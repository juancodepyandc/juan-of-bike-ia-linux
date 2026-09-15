# Entraînement Aurora : PC → Kaggle → comparaison locale

Le profil de pilotage est `/home/juan/Bureau/Aurora_Entrainement.json`.
Le raccourci `Aurora_Entrainement.desktop` lance ou reprend la campagne. Le centre
`cycle_app.py` affiche le module actif, les scores, les erreurs et les comparatifs.
La campagne étendue s'arrête après 18 heures au maximum ; chaque session Kaggle du profil
dure au plus une heure. Le fichier peut être modifié pour les campagnes suivantes.

## Utilisation

Depuis `/home/juan/AuroraIA` :

```bash
application/.venv/bin/python -m auto_rl.campaign status
application/.venv/bin/python -m auto_rl.campaign stop
application/.venv/bin/python -m auto_rl.campaign run --config /home/juan/Bureau/Aurora_Entrainement.json
application/.venv/bin/python -m auto_rl.cli doctor
application/.venv/bin/python -m auto_rl.cli models
```

Le bouton **Arrêter la campagne** arrête aussi le module courant. **Arrêter le
cycle** ne concerne que le module courant : la campagne peut ensuite passer au
suivant. Les campagnes terminées avec une erreur peuvent être relancées ; les
modules déjà acceptés ou rejetés sont conservés dans le journal du même profil.

Après une erreur d'envoi, les préférences déjà mesurées peuvent être réutilisées :

```bash
application/.venv/bin/python -m auto_rl.cli run --config Outputs/auto_rl/profiles/code.json --resume IDENTIFIANT_DU_CYCLE
```

Cette reprise réutilise les préférences déjà enregistrées ou reconstruit le lot à partir des essais conservés, puis relance l'optimisation. Ce n'est pas une
restauration exacte de l'état de l'optimiseur à l'époque interrompue.

## Parcours et limites actuelles

| Module | Entraînement | Mesure et intégration |
|---|---|---|
| Code | Préférences d'exécution, adaptateur Qwen3-8B | Tests Python dans Podman ; modèle sélectionnable après validation |
| Cyber / Cowork | Même moteur, tâches synthétiques de logique et traitement de données | Ne certifie pas la maîtrise générale des outils ni d'un environnement réel |
| Conversation | DPO entre réponses de référence calculées par un oracle et essais JSON du modèle | Mesure le raisonnement structuré, pas toute la qualité d'un dialogue |
| 3D | Préférences de rendus locaux ; entraînement du flux structurel dense TRELLIS sur Kaggle | Géométrie et vues comparées sur le PC ; adaptateur chargé par le wrapper TRELLIS après validation |
| Voix | Recherche évolutive dans un sous-espace de poids Kokoro | Transcription et signal audio ; adaptateur chargé dans le chemin Kokoro du service voix |
| Image | Essais FLUX.2 GGUF dans ComfyUI ; Kaggle ajuste un modèle de récompense et propose des coefficients LoRA | Audit des images réelles sur le PC ; adaptateur ComfyUI chargé après validation en CLI, UI et via le bridge |

| Vidéo | Corrections de poids Wan2.2 TI2V 5B ; essais ComfyUI locaux et coefficients optimisés sur Kaggle | 33 images, CLIP, mouvement et erreur après compensation du flux optique ; séquences réelles comparées avant promotion |
| Animation | Corrections de poids du transformeur HY-Motion ; optimisation des coefficients sur Kaggle | Squelette de 90 images, déplacements réels, glissement des pieds, stabilité des os et saccades ; wrapper de production raccordé |
| Apprentissage | DPO Qwen3-8B, réponses calculées par des oracles éducatifs | 18 compétences scolaires séparées par famille entre entraînement et audit ; calcul vérifiable, sans certification de pédagogie générale |

Les dix modules font partie de la campagne. Une erreur est enregistrée avant de
passer au suivant. Ajouter des modules conserve les audits terminés lorsque
leur profil et la révision du curriculum sont inchangés. Les anciens journaux
sont archivés dans `Outputs/auto_rl/campaign_history/`.

Les fichiers originaux des modèles restent inchangés. Les poids entraînés sont
stockés en `candidate.safetensors`, avec un rapport et une empreinte SHA-256.
L'optimisation s'arrête tôt si la validation ne progresse plus. Le registre ne
reçoit que les candidats admissibles : amélioration mesurée, absence de
régression au-delà de la tolérance configurée et audit suffisamment grand. Les
prompts répétés sont regroupés dans le calcul de confiance. Le service refait
ces contrôles avant de proposer un adaptateur.

Le gain est mesuré contre **la base exacte du formateur**. Une amélioration de
Qwen3-8B ne démontre pas qu'il dépasse les modèles 30B/32B déjà utilisés par
Aurora. Aucun modèle général plus puissant ni maximum absolu de performance
n'est garanti par ces tests. Les premiers lots peuvent être petits et rejetés.

Le parcours image optimise un petit sous-espace de poids : Kaggle reçoit les
coefficients et les scores mesurés, puis propose un candidat. FLUX.2 reste chargé
sur le PC par ComfyUI. La perte du modèle de récompense et son gain prédit ne sont
pas des preuves de qualité ; seuls les rendus réservés déterminent la promotion.
Le profil actuel utilise des images 512 × 512 à 8 étapes, comparées à réglages
identiques. Il ne prouve pas un gain à toutes les résolutions ni à tous les
nombres d'étapes. La VRAM ComfyUI est échantillonnée, pas mesurée en continu.

## Kaggle

Le lot explicite est une archive `payload.bin` dont le contenu est vérifié par
SHA-256 sur le worker. Cette extension empêche la décompression automatique du
ZIP par le dataset. Aucun répertoire personnel n'est envoyé. Aucun jeton du PC
n'est inséré dans le script. Les modèles publics utilisés par le parcours
préférences ne demandent pas de jeton.

Le code Kaggle et le dataset sont privés. Les erreurs de démarrage et les
résultats sont archivés dans `aurora_result.zip`. Les résultats doivent porter
l'identifiant du cycle et les empreintes attendues. Le statut de session de la
CLI Kaggle concerne la dernière version ; l'identifiant du lot et le manifeste
empêchent donc de confondre le résultat avec celui d'un autre entraînement.

Référence : [métadonnées officielles Kaggle](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md).

## CLI, interface et tunnel

Le service local `aurora-trained-models.service` écoute `127.0.0.1:11435`.
Il propose les modèles **validés uniquement**, sous des noms comme
`aurora-rl-code:v1`. Il ne remplace pas automatiquement le modèle de conversation
ou de code actuellement sélectionné. Exemple après validation :

```bash
application/.venv/bin/python -m auto_rl.cli chat aurora-rl-code:v1 "Explique ce problème."
```

Aurora ajoute ces modèles à la liste et dirige leur chat vers ce service.
Le bridge existant expose `/api/training/models`, `/api/training/status` et
`/proxy/trained/api/chat`. Le tunnel utilise les mêmes routes du bridge ; aucun
nouveau tunnel public n'est créé. Le profil texte est limité à 4096 tokens,
réponse comprise ; vision et appels d'outils ne sont pas pris en charge par ce
serveur d'adaptateurs. Une requête ne bascule pas silencieusement vers un modèle
de base si l'adaptateur manque.

Pour les images, `/api/training/image-workflow` raccorde l'adaptateur validé au
workflow du modèle GGUF correspondant. Les chemins Python de génération, la
soumission de l'interface et le proxy ComfyUI utilisent le même contrôle. Les
audits désactivent ce raccordement automatique pour garder une base intacte.

Le service libère le modèle après la réponse et partage le verrou d'entraînement
pour éviter de charger deux gros modèles simultanément. Cela ajoute un coût de
chargement à chaque requête. Kokoro reste le chemin Kokoro du service voix ; le
moteur Piper utilisé en priorité n'est pas transformé par son adaptateur.

## Fichiers utiles

- `Outputs/auto_rl/campaign.json` : état de chaque module.
- `Outputs/auto_rl/status.json` : état du cycle actif.
- `Outputs/auto_rl/campaign-MODULE.log` : journal détaillé.
- `Outputs/auto_rl/runs/IDENTIFIANT/comparison.html` : comparaison avant/après.
- `Outputs/auto_rl/runs/IDENTIFIANT/training_metrics.json` : métriques Kaggle.
- `Outputs/auto_rl/registry/` : adaptateurs acceptés.
- `Inputs/AutoRL/3D/A_TRAITER/` : références 3D avec descriptions JSON ou TXT.

Les références 3D sont dédupliquées ; les descriptions identiques ne sont pas
réutilisées à la fois pour apprentissage et audit. Les anciennes modifications
ont été sauvegardées dans `auto_rl/backups/repair-20260912-115413/`.

## Vérifications de cette réparation

Le 12 septembre 2026 : transfert privé Kaggle et GPU Tesla T4 vérifiés ;
entraînement LoRA réel testé en BF16 et FP16 ; production d'images ComfyUI GGUF
avec et sans adaptation vérifiée (les pixels changent, sans conclusion de gain).
Les tests couvrent notamment le bac à sable, les fuites entre apprentissage et
audit, les poids gelés, les transferts, les routes et le raccordement image.

L'ancien candidat `code-20260912-120421-47ab8a` a été retiré du registre parce que
son audit ne comportait que quatre prompts indépendants. Son dossier et son
rapport restent consultables ; la décision de quarantaine est conservée dans
`Outputs/auto_rl/quarantine/`. La nouvelle campagne doit produire ses propres
mesures avant qu'un modèle plus performant puisse être annoncé.

Pour la conversation, les références parfaites du lot sont des étiquettes
calculées par les oracles, jamais des réponses présentées comme produites par
le modèle. Leur provenance est enregistrée dans `*.supervision.json` et dans
`chosen_origin`. Seuls les sujets d'apprentissage fournissent ces étiquettes ;
l'audit génère de nouvelles réponses sur ses familles réservées.

La campagne du 12 septembre a terminé les parcours code, cyber, cowork, image
et audio avec audit. Aucun candidat n'a passé le seuil : gains moyens respectifs
de +0,52, +0,13, −0,52, +0,19 et 0 point, avec incertitude ou régression selon le
module. Ces nombres concernent uniquement les petits audits décrits dans les
rapports. Conversation a ensuite terminé son audit : +10,42 points en moyenne,
mais intervalle à 95 % [−2,08 ; +22,92] et une régression ; candidat rejeté.
TRELLIS a terminé 24 époques Kaggle avant une interruption mémoire pendant son
audit local. Le juge créait 14 475 objets de maillage ; le calcul par composantes
creuses a évalué le fichier problématique en 4,6 s et 1,4 Go de RAM. Le profil
`resume_audit` réutilise le candidat entraîné, recontrôle les empreintes et
réévalue les fichiers conservés. Il ne relance pas Kaggle.

Une reprise unique des modules en erreur peut attendre la campagne active avec :

```bash
application/.venv/bin/python -m auto_rl.campaign recover
```

Elle conserve la limite horaire de la campagne suivie, ne répète pas les audits
terminés et s'annule si la campagne est arrêtée ou remplacée. Le service de cette
reprise est `aurora-training-recovery.service`. La commande `campaign stop`
arrête aussi cette attente. Des rendus FLUX de base déjà produits peuvent servir
de références 3D ; les fichiers JSON de la file indiquent leur provenance et
leur SHA-256. Les poids d'un candidat image rejeté ne sont jamais employés pour
ces références.


## Extension du 13 septembre : vidéo, animation, apprentissage

La campagne active est `aurora-training-extended.service` : audit 3D repris,
puis apprentissage, animation et vidéo. Les six audits déjà terminés ne sont pas
relancés. Le service limite sa mémoire et son swap ; le rendu ComfyUI reste dans
son service existant. La campagne ne peut pas optimiser un maximum absolu de
qualité : elle produit des candidats mesurés sur les profils décrits ici.

Interface locale : http://127.0.0.1:3001/api/training/ui . Le même chemin est
accessible derrière le tunnel Aurora lorsqu'il est actif. Cette réparation ne
publie pas un nouveau tunnel ; aucun accès distant en direct n'a été validé.
L'interface affiche les dix modules et génère vidéo/animation en sélectionnant
explicitement « Modèle de base » ou « Candidat validé ». Sans candidat admissible,
la seconde option renvoie une erreur claire.

```bash
application/.venv/bin/python -m auto_rl.media video "A small boat sails across a lake" --base
application/.venv/bin/python -m auto_rl.media animation "A person waves with the right hand" --base
# Après validation : omettre --base pour appliquer le candidat audité.
```

La vidéo est exportée en MP4 H.264, avec la séquence WebP sans perte conservée.
Les fichiers produits par ces commandes se trouvent sous
`Outputs/auto_rl/generated/`. Les comparatifs vidéo sont animés ; les fichiers
NPZ d'animation sont accompagnés d'un lecteur HTML avec pause et curseur de temps.
Le module apprentissage apparaît après validation sous `aurora-rl-learning:v1`
dans la sélection des modèles Aurora. Le modèle explicitement choisi est conservé
par le sélecteur de raisonnement, y compris dans l'Académie.

Vérifications réelles : Wan2.2 a produit 33 images en 113 s ; le test avec une
correction non nulle change les pixels (MAE 10,77/255), sans constituer un audit
de gain. HY-Motion produit 90 images en 19,2 s et utilise 11,53 Go de VRAM ;
une correction change les articulations (MAE 0,00525 m). Son juge recalcule les
coordonnées mondiales, car les articulations du moteur étaient locales tandis
que la translation était séparée. Aucun de ces tests de raccordement ne valide
un candidat. Tests automatisés : 25 Python et 27 TypeScript, compilation native
réussie.

Les nouveaux poids vidéo sont ceux du [parcours officiel Wan2.2 de ComfyUI](https://docs.comfy.org/tutorials/video/wan/wan2_2),
installés sous `modele/comfyui/models/`. Le moteur 5B est évalué contre sa propre
base ; aucune supériorité sur les variantes 14B n'est annoncée. Le backend vidéo
historique `video_generate.py` est absent de cette installation : le parcours
vérifié passe par la nouvelle interface, la CLI média et ComfyUI. Les graphes
Wan compatibles reçoivent aussi l'adaptateur validé via le bridge ComfyUI.


## Session 3D autonome de 30 minutes

```bash
application/.venv/bin/python -m auto_rl.autonomous_session run
application/.venv/bin/python -m auto_rl.autonomous_session status
application/.venv/bin/python -m auto_rl.autonomous_session stop
```

Le raccourci `Aurora_3D_30min.desktop` lance ce parcours. Le service démarré
par l'assistant s'appelle `aurora-3d-autonomous.service`. La campagne précédente
est terminée ; cette session ne lance que le module 3D.

Les 1800 secondes limitent la supervision de l'apprentissage sur Kaggle,
y compris ses redémarrages et chargements de modèle. Le transfert, l'installation
du worker et l'audit des maillages sur le PC sont en plus. La limite du kernel
est de 45 minutes pour garder une marge de préparation et d'export. Il utilise
les préférences 3D réellement mesurées (2 pour apprendre, 1 pour valider).
Le peu de données limite les conclusions : aucune amélioration générale n'est
promise au terme des 30 minutes.

Le superviseur est un programme autonome, pas Codex qui surveille les étapes :

- Sauvegarde à chaque époque ; sélection des meilleurs poids selon la validation.
- Validation qui stagne : meilleurs poids restaurés, pas d'apprentissage réduit,
  nouveau bruit d'entraînement, optimiseur réinitialisé explicitement.
- Mémoire CUDA insuffisante : nouvelle tentative avec les tenseurs de gradient
  sauvegardés en RAM via [le mécanisme PyTorch](https://docs.pytorch.org/docs/stable/autograd.html#torch.autograd.graph.save_on_cpu).
- Calcul non fini : retour aux meilleurs poids finis, réduction du pas et du
  facteur FP16, au maximum deux corrections.
- Erreur inconnue, intégrité douteuse ou processus tué : arrêt et journal complet.

Pour les cycles locaux, `aurora-trained-models.service` est suspendu pendant
le chargement d'un modèle d'entraînement puis redémarré après l'audit. HY-Motion
garde son encodeur Qwen en RAM CPU et transfère seulement ses représentations ;
cela évite que l'encodeur et le DiT se disputent les 16 Go de la RTX. L'allocation
CUDA utilise des segments extensibles et un découpage limité pour réduire la
fragmentation. Le profil radical de la page sélectionne `gpu_t4_x2` et les
essais parallèles Kaggle ; le profil standard conserve le budget choisi.

En cas d'arrêt forcé manuel, utiliser :

```bash
systemctl --user kill --kill-whom=all --signal=SIGKILL 'aurora-training-*.service'
```

Les corrections sont limitées à ces stratégies et ne modifient ni les modèles
de base, ni les données réservées à l'audit, ni les seuils de promotion. Il ne
réécrit pas du code arbitraire à partir d'un message d'erreur. Les essais échoués,
les diagnostics et les paramètres de reprise sont conservés dans `autonomy.json`
et `attempt_*/attempt.log`, avec les empreintes des sauvegardes. Le journal global
est `Outputs/auto_rl/autonomous_3d.json`, visible dans l'interface web.

Vérification avant lancement : erreur CUDA simulée suivie d'une reprise automatique,
arrêt sur erreur inconnue, et deux époques réelles TRELLIS en FP16 dans chacun
des modes normal et sauvegarde en RAM. Les 43 tests Python passent. Le candidat
reste séparé jusqu'à l'audit local, qui compare de vrais maillages sur 8 sujets
réservés et 2 graines. Les rendus de base déjà mesurés sont réutilisés uniquement
si leurs empreintes et paramètres correspondent.

### Commandes web et CLI : cycles bornés ou continus

La page `http://127.0.0.1:3001/api/training/ui` contrôle maintenant les dix
modules. Elle sépare la session active, le dernier cycle de chaque module,
le dernier candidat entraîné et la dernière version validée. Les compteurs
avancent chaque seconde ; une perte de connexion les fige. Les résultats ne
proviennent plus de l'ancien tableau de campagne.

- **Un cycle** : budget Kaggle de 10 à 600 minutes, avec préparation,
  transferts et audit local en plus. Le profil radical utilise toute la durée
  choisie (marge d'export réservée) ; les essais PC restent bornés et les
  sorties mesurées sont réutilisées au cycle suivant.
- **En continu** : nouveaux cycles avec de nouvelles graines, depuis la base ou
  le champion validé disponible. Les candidats rejetés ne remplacent pas ce
  point de départ. Les refus de promotion ne stoppent pas la boucle. Le quota
  insuffisant déclenche une attente, contrôlée toutes les cinq minutes.
- **Arrêt propre** : termine le cycle en cours, exporte les poids et termine
  l'audit, puis s'arrête. Ce n'est pas un arrêt immédiat du kernel Kaggle ; selon
  le module, la fin du cycle peut prendre des dizaines de minutes ou davantage.
- **Changer après ce cycle** : même sauvegarde et audit, puis le nouveau module
  démarre avec les options choisies. Une demande d'arrêt suivante annule ce
  changement. Fermer l'onglet ou redémarrer le bridge ne coupe pas le superviseur.

```bash
application/.venv/bin/python -m auto_rl.control start --module 3d --continuous --minutes 30
application/.venv/bin/python -m auto_rl.control status
application/.venv/bin/python -m auto_rl.control switch --module video --continuous --minutes 20
application/.venv/bin/python -m auto_rl.control stop
application/.venv/bin/python aurora-universal-trainer.py select 3d base
application/.venv/bin/python aurora-universal-trainer.py select 3d validated
```

Le contrôleur est un service utilisateur `aurora-training-<session>.service`,
avec les limites mémoire déjà vérifiées pour TRELLIS. Son journal est
`Outputs/auto_rl/control.json`, ses profils/logs sont dans `control_sessions/`.
Les commandes sont liées à l'identifiant de session : un ancien stop ne coupe
pas un nouveau travail. Un seul contrôleur/cycle utilise le moteur à la fois.
Les erreurs inconnues arrêtent la boucle avec leur message ; les corrections
connues de l'apprentissage 3D restent celles du superviseur autonome existant.
Une extinction du PC ou un arrêt forcé du service reste une interruption.

Chaque module possède aussi une mémoire de cas difficiles dans
`Outputs/auto_rl/failure_memory/<module>.json`. Les sorties d'apprentissage
invalides ou sous le seuil sont enregistrées avec leur mesure, puis quelques
cas sont rejoués en priorité au cycle suivant. Les sujets d'audit ne sont
jamais écrits dans cette mémoire. Les préférences multimodales conservent
également un rendu invalide mesuré comme contre-exemple au lieu de le jeter.
Un arrêt ou un changement demandé au contrôleur écrit maintenant
`stop_signal.txt` dans le cycle enfant ; l'arrêt coopératif atteint donc le
processus qui utilise réellement le GPU et n'est pas classé comme une erreur.

La sélection d'inférence n'écrit jamais dans les poids de base. Par défaut,
Aurora utilise la base ; sélectionner `validated` nécessite un audit admissible.
Les wrappers TRELLIS, Flux, Wan, HY-Motion et Kokoro respectent cette préférence
à la prochaine génération. Une sélection explicite de voix sur cette page
choisit Kokoro, y compris lorsqu'un autre moteur vocal était prioritaire.
Les graphes ComfyUI déjà décorés sont nettoyés des seuls adaptateurs Aurora
lors du retour à la base.

Dans le catalogue texte d'Aurora et via `aurora-universal-trainer.py chat` :

- `aurora-rl-code:base` : Qwen3-8B d'origine, adaptateur désactivé.
- `aurora-rl-code:selected` : suit la préférence enregistrée sur la page.
- `aurora-rl-code:vN` : version précise validée, affichée après promotion.

Les mêmes suffixes existent pour conversation, cyber, cowork et learning.
Les poids du dernier candidat expérimental sont téléchargeables, mais un
candidat rejeté n'est pas annoncé comme modèle de production plus performant.
Les durées de rendus en cache issus de cycles différents sont signalées ;
elles ne prouvent pas une différence de vitesse dans les mêmes conditions.

Validation : 43 tests Python, interactions navigateur desktop/mobile avec
requêtes de contrôle simulées (aucun job GPU lancé par ces tests), et vraie
inférence de `aurora-rl-code:base` via le proxy Aurora : réponse reçue en 10,26 s.
Le dernier entraînement 3D a réalisé 69 époques en 1800,84 s, avec deux reprises
sur stagnation. Son audit donne −0,10 point : base conservée.

Le partage des familles apprentissage/audit reste fixe entre les cycles continus.
Les exemples textuels et les graines de génération varient ; les sujets média
sont conservés dans `control_curricula/`, même après déplacement des photos
validées. Le démarrage réel du service et la prise en compte d’un arrêt déjà
demandé ont aussi été vérifiés, sans lancer de job GPU.
