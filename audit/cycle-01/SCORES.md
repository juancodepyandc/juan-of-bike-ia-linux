# Notes du cycle 1

J ×3, R ×2, T ×3, A ×2, C ×2, O ×1, S ×2, D ×1. Somme des poids : 16.

J : justesse ; R : robustesse ; T : choix technique ; A : architecture ; C : tests ; O : observabilité ; S : sécurité ; D : lisibilité.

Notes provisoires des unités effectivement relues. Le choix du meilleur modèle actuel et la qualité des rendus ne sont pas établis par ces notes. Les autres unités restent explicitement non évaluées dans le registre ; elles ne reçoivent aucune note par défaut. Pour les fichiers et le module AGI, chaque critère retient le minimum des fonctions publiques revues, afin de ne pas masquer un défaut grave.

| Unité | J | R | T | A | C | O | S | D | Pondéré |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| module · agi_core | 1 | 2 | 1 | 2 | 1 | 1 | 1 | 3 | 1.38 |
| file · agi_core/explorer.py | 1 | 2 | 1 | 3 | 1 | 1 | 3 | 3 | 1.75 |
| function · DeepDiscoveryEngine.explore_unknown | 1 | 2 | 1 | 3 | 1 | 1 | 3 | 3 | 1.75 |
| file · agi_core/mission_agent.py | 2 | 2 | 3 | 2 | 1 | 3 | 1 | 3 | 2.06 |
| function · AutonomousMissionAgent.run | 2 | 2 | 3 | 2 | 1 | 3 | 1 | 3 | 2.06 |
| function · JOBIACore.process_request | 2 | 2 | 3 | 5 | 1 | 2 | 5 | 5 | 3.00 |
| file · agi_core/payload_manager.py | 4 | 3 | 3 | 4 | 1 | 3 | 2 | 5 | 3.06 |
| function · SmartPayloadManager.package_for_client | 4 | 3 | 3 | 4 | 1 | 3 | 2 | 5 | 3.06 |
| function · init_app_dirs | 2 | 3 | 5 | 5 | 1 | 1 | 3 | 5 | 3.19 |
| file · aurora_agi_daemon.py | 3 | 3 | 3 | 5 | 2 | 4 | 3 | 5 | 3.31 |
| function · check_for_previous_crashes | 3 | 3 | 3 | 5 | 2 | 4 | 3 | 5 | 3.31 |
| file · agi_core/bus.py | 4 | 3 | 4 | 5 | 2 | 3 | 2 | 4 | 3.44 |
| file · agi_core/consciousness.py | 3 | 3 | 3 | 5 | 2 | 4 | 4 | 5 | 3.44 |
| function · AsyncEventBus.publish | 4 | 3 | 4 | 5 | 2 | 3 | 2 | 4 | 3.44 |
| function · AGICortex.run_continuous_loop | 3 | 3 | 3 | 5 | 2 | 4 | 4 | 5 | 3.44 |
| function · publish_sync | 4 | 3 | 4 | 5 | 2 | 3 | 3 | 5 | 3.62 |
| file · agi_core/memory.py | 5 | 3 | 4 | 5 | 2 | 4 | 3 | 6 | 3.94 |
| function · OmniscientMemory.embed_experience | 5 | 3 | 4 | 5 | 2 | 4 | 3 | 6 | 3.94 |
| function · OmniscientMemory.query_experience | 5 | 3 | 4 | 5 | 2 | 4 | 3 | 6 | 3.94 |
| function · save | 6 | 2 | 4 | 6 | 3 | 2 | 2 | 6 | 4.00 |
| file · agi_core/swarm.py | 5 | 4 | 4 | 6 | 2 | 5 | 4 | 6 | 4.38 |
| function · SwarmSupervisor.delegate | 5 | 4 | 4 | 6 | 2 | 5 | 5 | 6 | 4.50 |
| function · main | 5 | 3 | 5 | 6 | 3 | 5 | 4 | 6 | 4.56 |
| file · agi_core/llm_gateway.py | 5 | 3 | 4 | 6 | 2 | 3 | 8 | 6 | 4.62 |
| function · AuroraClient.stream_sse | 4 | 3 | 5 | 6 | 5 | 3 | 5 | 6 | 4.62 |
| function · AsyncEventBus.start_server | 6 | 4 | 5 | 6 | 2 | 5 | 3 | 6 | 4.62 |
| function · AsyncEventBus.subscribe | 6 | 4 | 5 | 6 | 2 | 5 | 3 | 6 | 4.62 |
| function · LLMGateway.generate_stream | 5 | 3 | 4 | 6 | 2 | 3 | 8 | 6 | 4.62 |
| function · LLMGateway.generate | 5 | 3 | 4 | 6 | 2 | 4 | 8 | 6 | 4.69 |
| function · SwarmSupervisor.run_mission | 5 | 4 | 4 | 6 | 5 | 5 | 4 | 6 | 4.75 |
| function · load | 6 | 3 | 5 | 6 | 6 | 2 | 3 | 6 | 4.81 |
| function · AuroraClient.delete | 6 | 4 | 6 | 6 | 3 | 4 | 5 | 7 | 5.19 |
| function · AuroraClient.get | 6 | 4 | 6 | 6 | 4 | 4 | 5 | 7 | 5.31 |
| function · AuroraClient.post | 6 | 4 | 6 | 6 | 4 | 4 | 5 | 7 | 5.31 |
| file · aurora_cli.py | 7 | 5 | 6 | 7 | 7 | 5 | 5 | 8 | 6.25 |
| function · main | 7 | 5 | 6 | 7 | 7 | 5 | 5 | 8 | 6.25 |
| function · is_configured | 8 | 6 | 7 | 8 | 8 | 5 | 6 | 8 | 7.12 |
| function · resolve_server_url | 9 | 8 | 8 | 9 | 9 | 7 | 8 | 9 | 8.44 |

Chaque critère inférieur à 7 est justifié ci-dessous. Les références sont relatives à la racine AuroraIA.

- module `agi_core` — justesse 1/10 : `agi_core/explorer.py:26: annonce zéro faille sans analyse`.
- module `agi_core` — robustesse 2/10 : `agi_core/explorer.py:17: boucle sans traitement des erreurs de publication`.
- module `agi_core` — choix_technique 1/10 : `agi_core/explorer.py:18: simulation, aucun moteur de découverte`.
- module `agi_core` — architecture 2/10 : `agi_core/mission_agent.py:19: contexte remplacé par des compteurs constants`.
- module `agi_core` — tests 1/10 : `agi_core/explorer.py:26: aucun test de découverte dans les fichiers suivis inventoriés`.
- module `agi_core` — observabilite 1/10 : `agi_core/explorer.py:19: logs sans mesure`.
- module `agi_core` — securite 1/10 : `agi_core/mission_agent.py:285: permissions non appliquées à l’écriture et chemin non confiné`.
- module `agi_core` — lisibilite 3/10 : `agi_core/explorer.py:21: fonctionnalité décrite uniquement en commentaires`.
- file `agi_core/explorer.py` — justesse 1/10 : `agi_core/explorer.py:26: annonce zéro faille sans analyse`.
- file `agi_core/explorer.py` — robustesse 2/10 : `agi_core/explorer.py:17: boucle sans traitement des erreurs de publication`.
- file `agi_core/explorer.py` — choix_technique 1/10 : `agi_core/explorer.py:18: simulation, aucun moteur de découverte`.
- file `agi_core/explorer.py` — architecture 3/10 : `agi_core/explorer.py:15: aucune entrée ni résultat vérifiable`.
- file `agi_core/explorer.py` — tests 1/10 : `agi_core/explorer.py:26: aucun test de découverte dans les fichiers suivis inventoriés`.
- file `agi_core/explorer.py` — observabilite 1/10 : `agi_core/explorer.py:19: logs sans mesure`.
- file `agi_core/explorer.py` — securite 3/10 : `agi_core/explorer.py:26: déclaration de sécurité sans preuve`.
- file `agi_core/explorer.py` — lisibilite 3/10 : `agi_core/explorer.py:21: fonctionnalité décrite uniquement en commentaires`.
- function `DeepDiscoveryEngine.explore_unknown` — justesse 1/10 : `agi_core/explorer.py:26: annonce zéro faille sans analyse`.
- function `DeepDiscoveryEngine.explore_unknown` — robustesse 2/10 : `agi_core/explorer.py:17: boucle sans traitement des erreurs de publication`.
- function `DeepDiscoveryEngine.explore_unknown` — choix_technique 1/10 : `agi_core/explorer.py:18: simulation, aucun moteur de découverte`.
- function `DeepDiscoveryEngine.explore_unknown` — architecture 3/10 : `agi_core/explorer.py:15: aucune entrée ni résultat vérifiable`.
- function `DeepDiscoveryEngine.explore_unknown` — tests 1/10 : `agi_core/explorer.py:26: aucun test de découverte dans les fichiers suivis inventoriés`.
- function `DeepDiscoveryEngine.explore_unknown` — observabilite 1/10 : `agi_core/explorer.py:19: logs sans mesure`.
- function `DeepDiscoveryEngine.explore_unknown` — securite 3/10 : `agi_core/explorer.py:26: déclaration de sécurité sans preuve`.
- function `DeepDiscoveryEngine.explore_unknown` — lisibilite 3/10 : `agi_core/explorer.py:21: fonctionnalité décrite uniquement en commentaires`.
- file `agi_core/mission_agent.py` — justesse 2/10 : `agi_core/mission_agent.py:299: texte sans appel outil accepté comme mission accomplie`.
- file `agi_core/mission_agent.py` — robustesse 2/10 : `agi_core/mission_agent.py:228: itération requests synchrone dans une coroutine`.
- file `agi_core/mission_agent.py` — choix_technique 3/10 : `agi_core/mission_agent.py:240: extraction par regex et actions sans schéma validé`.
- file `agi_core/mission_agent.py` — architecture 2/10 : `agi_core/mission_agent.py:19: contexte remplacé par des compteurs constants`.
- file `agi_core/mission_agent.py` — tests 1/10 : `agi_core/mission_agent.py:161: aucun test direct du moteur avec exécution contrôlée avant cet audit`.
- file `agi_core/mission_agent.py` — observabilite 3/10 : `agi_core/mission_agent.py:277: code de sortie perdu, sortie vide transformée en succès`.
- file `agi_core/mission_agent.py` — securite 1/10 : `agi_core/mission_agent.py:285: permissions non appliquées à l’écriture et chemin non confiné`.
- file `agi_core/mission_agent.py` — lisibilite 3/10 : `agi_core/mission_agent.py:203: noms de dossiers de transfert contradictoires`.
- function `AutonomousMissionAgent.run` — justesse 2/10 : `agi_core/mission_agent.py:299: texte sans appel outil accepté comme mission accomplie`.
- function `AutonomousMissionAgent.run` — robustesse 2/10 : `agi_core/mission_agent.py:228: itération requests synchrone dans une coroutine`.
- function `AutonomousMissionAgent.run` — choix_technique 3/10 : `agi_core/mission_agent.py:240: extraction par regex et actions sans schéma validé`.
- function `AutonomousMissionAgent.run` — architecture 2/10 : `agi_core/mission_agent.py:19: contexte remplacé par des compteurs constants`.
- function `AutonomousMissionAgent.run` — tests 1/10 : `agi_core/mission_agent.py:161: aucun test direct du moteur avec exécution contrôlée avant cet audit`.
- function `AutonomousMissionAgent.run` — observabilite 3/10 : `agi_core/mission_agent.py:277: code de sortie perdu, sortie vide transformée en succès`.
- function `AutonomousMissionAgent.run` — securite 1/10 : `agi_core/mission_agent.py:285: permissions non appliquées à l’écriture et chemin non confiné`.
- function `AutonomousMissionAgent.run` — lisibilite 3/10 : `agi_core/mission_agent.py:203: noms de dossiers de transfert contradictoires`.
- function `JOBIACore.process_request` — justesse 2/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:56: callback success même en cas d’erreur distante`.
- function `JOBIACore.process_request` — robustesse 2/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:43: fin de flux sans mission_complete acceptée`.
- function `JOBIACore.process_request` — choix_technique 3/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:26: identifiant limité à l’heure à la seconde`.
- function `JOBIACore.process_request` — architecture 5/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:37: mode demandé jamais transmis`.
- function `JOBIACore.process_request` — tests 1/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:25: aucun test de callback de cette API dans ce cycle`.
- function `JOBIACore.process_request` — observabilite 2/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:44: seuls les tokens sont consommés`.
- function `JOBIACore.process_request` — securite 5/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:25: état de mission non isolé par identifiant serveur`.
- function `JOBIACore.process_request` — lisibilite 5/10 : `../aurora-remote-cli/aurora_cli/core/jobia.py:54: erreur représentée par une chaîne de résultat`.
- file `agi_core/payload_manager.py` — justesse 4/10 : `agi_core/payload_manager.py:38: renvoie un chemin serveur à un PC distant`.
- file `agi_core/payload_manager.py` — robustesse 3/10 : `agi_core/payload_manager.py:26: lecture et encodage intégraux en RAM`.
- file `agi_core/payload_manager.py` — choix_technique 3/10 : `agi_core/payload_manager.py:26: base64 monolithique pour des artefacts volumineux`.
- file `agi_core/payload_manager.py` — architecture 4/10 : `agi_core/payload_manager.py:22: protocole différent selon le terminal`.
- file `agi_core/payload_manager.py` — tests 1/10 : `agi_core/payload_manager.py:15: pas de test de transfert du fichier produit`.
- file `agi_core/payload_manager.py` — observabilite 3/10 : `agi_core/payload_manager.py:20: seul le formatage est journalisé`.
- file `agi_core/payload_manager.py` — securite 2/10 : `agi_core/payload_manager.py:25: aucun contrôle du périmètre de lecture`.
- file `agi_core/payload_manager.py` — lisibilite 5/10 : `agi_core/payload_manager.py:22: deux branches sans contrat commun versionné`.
- function `SmartPayloadManager.package_for_client` — justesse 4/10 : `agi_core/payload_manager.py:38: renvoie un chemin serveur à un PC distant`.
- function `SmartPayloadManager.package_for_client` — robustesse 3/10 : `agi_core/payload_manager.py:26: lecture et encodage intégraux en RAM`.
- function `SmartPayloadManager.package_for_client` — choix_technique 3/10 : `agi_core/payload_manager.py:26: base64 monolithique pour des artefacts volumineux`.
- function `SmartPayloadManager.package_for_client` — architecture 4/10 : `agi_core/payload_manager.py:22: protocole différent selon le terminal`.
- function `SmartPayloadManager.package_for_client` — tests 1/10 : `agi_core/payload_manager.py:15: pas de test de transfert du fichier produit`.
- function `SmartPayloadManager.package_for_client` — observabilite 3/10 : `agi_core/payload_manager.py:20: seul le formatage est journalisé`.
- function `SmartPayloadManager.package_for_client` — securite 2/10 : `agi_core/payload_manager.py:25: aucun contrôle du périmètre de lecture`.
- function `SmartPayloadManager.package_for_client` — lisibilite 5/10 : `agi_core/payload_manager.py:22: deux branches sans contrat commun versionné`.
- function `init_app_dirs` — justesse 2/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:25: crée les destinations avant les conditions de migration`.
- function `init_app_dirs` — robustesse 3/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:31: dossiers sources ne peuvent plus être migrés après leur création`.
- function `init_app_dirs` — choix_technique 5/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:6: XDG utilisé mais règle de migration incohérente`.
- function `init_app_dirs` — architecture 5/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:43: effets de bord à l’import`.
- function `init_app_dirs` — tests 1/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:23: migration réelle non testée dans ce cycle`.
- function `init_app_dirs` — observabilite 1/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:39: échec de nettoyage ignoré`.
- function `init_app_dirs` — securite 3/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:26: permissions laissées à l’umask pour les données locales`.
- function `init_app_dirs` — lisibilite 5/10 : `../aurora-remote-cli/aurora_cli/core/paths.py:31: branches de migration inatteignables`.
- file `aurora_agi_daemon.py` — justesse 3/10 : `aurora_agi_daemon.py:35: log supprimé avant réussite du diagnostic`.
- file `aurora_agi_daemon.py` — robustesse 3/10 : `aurora_agi_daemon.py:18: lecture intégrale du journal`.
- file `aurora_agi_daemon.py` — choix_technique 3/10 : `aurora_agi_daemon.py:24: réponse textuelle confondue avec guérison`.
- file `aurora_agi_daemon.py` — architecture 5/10 : `aurora_agi_daemon.py:15: état de reprise dépendant du dossier temporaire`.
- file `aurora_agi_daemon.py` — tests 2/10 : `aurora_agi_daemon.py:13: pas de test d’échec de cette reprise`.
- file `aurora_agi_daemon.py` — observabilite 4/10 : `aurora_agi_daemon.py:36: preuve du crash remplacée`.
- file `aurora_agi_daemon.py` — securite 3/10 : `aurora_agi_daemon.py:35: réécriture destructive des traces`.
- file `aurora_agi_daemon.py` — lisibilite 5/10 : `aurora_agi_daemon.py:32: callback ne traite pas l’annulation`.
- function `check_for_previous_crashes` — justesse 3/10 : `aurora_agi_daemon.py:35: log supprimé avant réussite du diagnostic`.
- function `check_for_previous_crashes` — robustesse 3/10 : `aurora_agi_daemon.py:18: lecture intégrale du journal`.
- function `check_for_previous_crashes` — choix_technique 3/10 : `aurora_agi_daemon.py:24: réponse textuelle confondue avec guérison`.
- function `check_for_previous_crashes` — architecture 5/10 : `aurora_agi_daemon.py:15: état de reprise dépendant du dossier temporaire`.
- function `check_for_previous_crashes` — tests 2/10 : `aurora_agi_daemon.py:13: pas de test d’échec de cette reprise`.
- function `check_for_previous_crashes` — observabilite 4/10 : `aurora_agi_daemon.py:36: preuve du crash remplacée`.
- function `check_for_previous_crashes` — securite 3/10 : `aurora_agi_daemon.py:35: réécriture destructive des traces`.
- function `check_for_previous_crashes` — lisibilite 5/10 : `aurora_agi_daemon.py:32: callback ne traite pas l’annulation`.
- file `agi_core/bus.py` — justesse 4/10 : `agi_core/bus.py:98: diffuse vers tous les clients sans tenir compte des abonnements`.
- file `agi_core/bus.py` — robustesse 3/10 : `agi_core/bus.py:101: un client lent peut bloquer le bus`.
- file `agi_core/bus.py` — choix_technique 4/10 : `agi_core/bus.py:97: sérialisation JSON sans limite explicite ni schéma`.
- file `agi_core/bus.py` — architecture 5/10 : `agi_core/bus.py:96: livraison locale et distante sans accusé de réception`.
- file `agi_core/bus.py` — tests 2/10 : `agi_core/bus.py:20: aucun test de reconnexion IPC ajouté dans ce cycle`.
- file `agi_core/bus.py` — observabilite 3/10 : `agi_core/bus.py:102: exception de livraison supprimée`.
- file `agi_core/bus.py` — securite 2/10 : `agi_core/bus.py:98: fuite de missions entre abonnés locaux`.
- file `agi_core/bus.py` — lisibilite 4/10 : `agi_core/bus.py:103: client écarté sans fermeture explicite`.
- file `agi_core/consciousness.py` — justesse 3/10 : `agi_core/consciousness.py:53: analyse textuelle ne produit ni correctif ni validation`.
- file `agi_core/consciousness.py` — robustesse 3/10 : `agi_core/consciousness.py:53: même souvenir peut être réanalysé indéfiniment`.
- file `agi_core/consciousness.py` — choix_technique 3/10 : `agi_core/consciousness.py:50: recherche littérale Error Exception Crash Traceback`.
- file `agi_core/consciousness.py` — architecture 5/10 : `agi_core/consciousness.py:45: planification par temporisation constante`.
- file `agi_core/consciousness.py` — tests 2/10 : `agi_core/consciousness.py:41: boucle réelle non couverte par un test de reprise`.
- file `agi_core/consciousness.py` — observabilite 4/10 : `agi_core/consciousness.py:52: aucune preuve de réparation stockée`.
- file `agi_core/consciousness.py` — securite 4/10 : `agi_core/consciousness.py:50: accès à une mémoire globale sans scope`.
- file `agi_core/consciousness.py` — lisibilite 5/10 : `agi_core/consciousness.py:42: docstring auto-optimisation excède le comportement`.
- function `AsyncEventBus.publish` — justesse 4/10 : `agi_core/bus.py:98: diffuse vers tous les clients sans tenir compte des abonnements`.
- function `AsyncEventBus.publish` — robustesse 3/10 : `agi_core/bus.py:101: un client lent peut bloquer le bus`.
- function `AsyncEventBus.publish` — choix_technique 4/10 : `agi_core/bus.py:97: sérialisation JSON sans limite explicite ni schéma`.
- function `AsyncEventBus.publish` — architecture 5/10 : `agi_core/bus.py:96: livraison locale et distante sans accusé de réception`.
- function `AsyncEventBus.publish` — tests 2/10 : `agi_core/bus.py:94: diffusion réelle non couverte dans ce cycle`.
- function `AsyncEventBus.publish` — observabilite 3/10 : `agi_core/bus.py:102: exception de livraison supprimée`.
- function `AsyncEventBus.publish` — securite 2/10 : `agi_core/bus.py:98: fuite de missions entre abonnés locaux`.
- function `AsyncEventBus.publish` — lisibilite 4/10 : `agi_core/bus.py:103: client écarté sans fermeture explicite`.
- function `AGICortex.run_continuous_loop` — justesse 3/10 : `agi_core/consciousness.py:53: analyse textuelle ne produit ni correctif ni validation`.
- function `AGICortex.run_continuous_loop` — robustesse 3/10 : `agi_core/consciousness.py:53: même souvenir peut être réanalysé indéfiniment`.
- function `AGICortex.run_continuous_loop` — choix_technique 3/10 : `agi_core/consciousness.py:50: recherche littérale Error Exception Crash Traceback`.
- function `AGICortex.run_continuous_loop` — architecture 5/10 : `agi_core/consciousness.py:45: planification par temporisation constante`.
- function `AGICortex.run_continuous_loop` — tests 2/10 : `agi_core/consciousness.py:41: boucle réelle non couverte par un test de reprise`.
- function `AGICortex.run_continuous_loop` — observabilite 4/10 : `agi_core/consciousness.py:52: aucune preuve de réparation stockée`.
- function `AGICortex.run_continuous_loop` — securite 4/10 : `agi_core/consciousness.py:50: accès à une mémoire globale sans scope`.
- function `AGICortex.run_continuous_loop` — lisibilite 5/10 : `agi_core/consciousness.py:42: docstring auto-optimisation excède le comportement`.
- function `publish_sync` — justesse 4/10 : `agi_core/bus.py:114: échec masqué au demandeur`.
- function `publish_sync` — robustesse 3/10 : `agi_core/bus.py:112: absence d’accusé de réception`.
- function `publish_sync` — choix_technique 4/10 : `agi_core/bus.py:111: message sans version ni validation`.
- function `publish_sync` — architecture 5/10 : `agi_core/bus.py:105: implémentation recopiée dans les routes CLI`.
- function `publish_sync` — tests 2/10 : `agi_core/bus.py:105: aucun test d’échec de livraison IPC dans ce cycle`.
- function `publish_sync` — observabilite 3/10 : `agi_core/bus.py:114: warning sans état de requête retourné`.
- function `publish_sync` — securite 3/10 : `agi_core/bus.py:110: bus sans authentification locale`.
- function `publish_sync` — lisibilite 5/10 : `agi_core/bus.py:109: timeout et port codés en dur`.
- file `agi_core/memory.py` — justesse 5/10 : `agi_core/memory.py:25: aucune mémorisation lorsque Chroma est absent`.
- file `agi_core/memory.py` — robustesse 3/10 : `agi_core/memory.py:31: erreur de persistance propagée après une mission`.
- file `agi_core/memory.py` — choix_technique 4/10 : `agi_core/memory.py:19: embedding implicite et non versionné`.
- file `agi_core/memory.py` — architecture 5/10 : `agi_core/memory.py:10: chemin absolu lié à cette machine`.
- file `agi_core/memory.py` — tests 2/10 : `agi_core/memory.py:24: persistance réelle non couverte par les tests ajoutés`.
- file `agi_core/memory.py` — observabilite 4/10 : `agi_core/memory.py:22: mémoire dite volatile alors qu’aucun stockage de repli existe`.
- file `agi_core/memory.py` — securite 3/10 : `agi_core/memory.py:28: stockage de contextes sans attribution obligatoire à un client`.
- file `agi_core/memory.py` — lisibilite 6/10 : `agi_core/memory.py:31: métadonnées par défaut non validées`.
- function `OmniscientMemory.embed_experience` — justesse 5/10 : `agi_core/memory.py:25: aucune mémorisation lorsque Chroma est absent`.
- function `OmniscientMemory.embed_experience` — robustesse 3/10 : `agi_core/memory.py:31: erreur de persistance propagée après une mission`.
- function `OmniscientMemory.embed_experience` — choix_technique 4/10 : `agi_core/memory.py:19: embedding implicite et non versionné`.
- function `OmniscientMemory.embed_experience` — architecture 5/10 : `agi_core/memory.py:10: chemin absolu lié à cette machine`.
- function `OmniscientMemory.embed_experience` — tests 2/10 : `agi_core/memory.py:24: persistance réelle non couverte par les tests ajoutés`.
- function `OmniscientMemory.embed_experience` — observabilite 4/10 : `agi_core/memory.py:22: mémoire dite volatile alors qu’aucun stockage de repli existe`.
- function `OmniscientMemory.embed_experience` — securite 3/10 : `agi_core/memory.py:28: stockage de contextes sans attribution obligatoire à un client`.
- function `OmniscientMemory.embed_experience` — lisibilite 6/10 : `agi_core/memory.py:31: métadonnées par défaut non validées`.
- function `OmniscientMemory.query_experience` — justesse 5/10 : `agi_core/memory.py:40: recherche sans filtre workspace/client`.
- function `OmniscientMemory.query_experience` — robustesse 3/10 : `agi_core/memory.py:40: n_results non validé et erreurs non contextualisées`.
- function `OmniscientMemory.query_experience` — choix_technique 4/10 : `agi_core/memory.py:19: embedding implicite non versionné`.
- function `OmniscientMemory.query_experience` — architecture 5/10 : `agi_core/memory.py:10: chemin de base lié à cette machine`.
- function `OmniscientMemory.query_experience` — tests 2/10 : `agi_core/memory.py:35: pertinence et rappel non mesurés`.
- function `OmniscientMemory.query_experience` — observabilite 4/10 : `agi_core/memory.py:40: pas de mesure de pertinence ni journal de récupération`.
- function `OmniscientMemory.query_experience` — securite 3/10 : `agi_core/memory.py:40: souvenirs de tous les clients dans la même collection`.
- function `OmniscientMemory.query_experience` — lisibilite 6/10 : `agi_core/memory.py:43: forme des résultats supposée`.
- function `save` — justesse 6/10 : `../aurora-remote-cli/aurora_cli/config.py:49: interruption peut tronquer la configuration`.
- function `save` — robustesse 2/10 : `../aurora-remote-cli/aurora_cli/config.py:49: écriture non atomique`.
- function `save` — choix_technique 4/10 : `../aurora-remote-cli/aurora_cli/config.py:49: pas de remplacement transactionnel`.
- function `save` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/config.py:49: données persistées sans version de schéma`.
- function `save` — tests 3/10 : `../aurora-remote-cli/aurora_cli/config.py:47: résistance au crash non testée ici`.
- function `save` — observabilite 2/10 : `../aurora-remote-cli/aurora_cli/config.py:49: pas de signal de validation après écriture`.
- function `save` — securite 2/10 : `../aurora-remote-cli/aurora_cli/config.py:49: permissions du fichier de clé laissées à l’umask`.
- function `save` — lisibilite 6/10 : `../aurora-remote-cli/aurora_cli/config.py:49: pas de validation des valeurs`.
- file `agi_core/swarm.py` — justesse 5/10 : `agi_core/swarm.py:69: plan dit validé sans exécution de vérification`.
- file `agi_core/swarm.py` — robustesse 4/10 : `agi_core/swarm.py:48: retour d’erreur du LLM seulement journalisé, pipeline poursuivi`.
- file `agi_core/swarm.py` — choix_technique 4/10 : `agi_core/swarm.py:52: choix du plan par texte libre sans critère objectif`.
- file `agi_core/swarm.py` — architecture 6/10 : `agi_core/swarm.py:69: planification distincte du pipeline conversation TypeScript`.
- file `agi_core/swarm.py` — tests 2/10 : `agi_core/swarm.py:94: pas de test direct de délégation dans ce cycle`.
- file `agi_core/swarm.py` — observabilite 5/10 : `agi_core/swarm.py:61: sorties de planification mélangées au flux final`.
- file `agi_core/swarm.py` — securite 4/10 : `agi_core/swarm.py:76: permissions relayées mais non appliquées par l’agent appelé`.
- file `agi_core/swarm.py` — lisibilite 6/10 : `agi_core/swarm.py:35: chaîne de prompts sans contrat de plan versionné`.
- function `SwarmSupervisor.delegate` — justesse 5/10 : `agi_core/swarm.py:107: renvoie la collecte même si la passerelle a renvoyé une erreur`.
- function `SwarmSupervisor.delegate` — robustesse 4/10 : `agi_core/swarm.py:105: aucun statut d’échec fourni au demandeur`.
- function `SwarmSupervisor.delegate` — choix_technique 4/10 : `agi_core/swarm.py:105: modèle de 48.19 GiB fixé dans le code`.
- function `SwarmSupervisor.delegate` — architecture 6/10 : `agi_core/swarm.py:105: sélection du modèle hors routeur partagé`.
- function `SwarmSupervisor.delegate` — tests 2/10 : `agi_core/swarm.py:94: pas de test direct de délégation dans ce cycle`.
- function `SwarmSupervisor.delegate` — observabilite 5/10 : `agi_core/swarm.py:106: résultat partiel journalisé sans identifiant de tâche`.
- function `SwarmSupervisor.delegate` — securite 5/10 : `agi_core/swarm.py:96: tâche potentiellement sensible écrite dans les logs`.
- function `SwarmSupervisor.delegate` — lisibilite 6/10 : `agi_core/swarm.py:107: chaîne seule sans résultat typé`.
- function `main` — justesse 5/10 : `aurora_agi_daemon.py:62: seul mission.start est enregistré, mission.stop absent`.
- function `main` — robustesse 3/10 : `aurora_agi_daemon.py:52: tâches créées sans registre de reprise`.
- function `main` — choix_technique 5/10 : `aurora_agi_daemon.py:64: pas d’état durable de l’ordonnanceur`.
- function `main` — architecture 6/10 : `aurora_agi_daemon.py:52: transport et cycle de vie des tâches non séparés`.
- function `main` — tests 3/10 : `aurora_agi_daemon.py:52: superviseur testé, démarrage complet non rejoué`.
- function `main` — observabilite 5/10 : `aurora_agi_daemon.py:60: callback sans statut persistant`.
- function `main` — securite 4/10 : `aurora_agi_daemon.py:50: payload non validé avant lancement`.
- function `main` — lisibilite 6/10 : `aurora_agi_daemon.py:60: callback ne traite pas l’annulation`.
- file `agi_core/llm_gateway.py` — justesse 5/10 : `agi_core/llm_gateway.py:38: erreur HTTP transformée en texte de résultat`.
- file `agi_core/llm_gateway.py` — robustesse 3/10 : `agi_core/llm_gateway.py:31: timeout total fixe et aucune reprise qualifiée`.
- file `agi_core/llm_gateway.py` — choix_technique 4/10 : `agi_core/llm_gateway.py:12: modèle par défaut mistral absent de l’inventaire Ollama`.
- file `agi_core/llm_gateway.py` — architecture 6/10 : `agi_core/llm_gateway.py:23: contexte codé en dur indépendamment du routage`.
- file `agi_core/llm_gateway.py` — tests 2/10 : `agi_core/llm_gateway.py:14: aucun benchmark de qualité réel exécuté dans ce cycle`.
- file `agi_core/llm_gateway.py` — observabilite 3/10 : `agi_core/llm_gateway.py:76: exception renvoyée sans log corrélé`.
- file `agi_core/llm_gateway.py` — lisibilite 6/10 : `agi_core/llm_gateway.py:38: succès et erreur partagent le même type`.
- function `AuroraClient.stream_sse` — justesse 4/10 : `../aurora-remote-cli/aurora_cli/client.py:84: ne reconnaît que data suivi de deux-points puis espace`.
- function `AuroraClient.stream_sse` — robustesse 3/10 : `../aurora-remote-cli/aurora_cli/client.py:87: JSON invalide supprimé silencieusement`.
- function `AuroraClient.stream_sse` — choix_technique 5/10 : `../aurora-remote-cli/aurora_cli/client.py:83: pas de reconstruction des événements SSE multilignes`.
- function `AuroraClient.stream_sse` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/client.py:69: crée un second client HTTP avec sa propre configuration`.
- function `AuroraClient.stream_sse` — tests 5/10 : `../aurora-remote-cli/aurora_cli/client.py:67: chemin terminal HTTP testé, fragmentation et reprise non testées`.
- function `AuroraClient.stream_sse` — observabilite 3/10 : `../aurora-remote-cli/aurora_cli/client.py:88: absence de compteurs d’événements perdus`.
- function `AuroraClient.stream_sse` — securite 5/10 : `../aurora-remote-cli/aurora_cli/client.py:74: même clé réutilisée sans contrat de version du serveur`.
- function `AuroraClient.stream_sse` — lisibilite 6/10 : `../aurora-remote-cli/aurora_cli/client.py:75: durée 600 secondes codée en dur`.
- function `AsyncEventBus.start_server` — justesse 6/10 : `agi_core/bus.py:22: aucune négociation de version du protocole`.
- function `AsyncEventBus.start_server` — robustesse 4/10 : `agi_core/bus.py:22: aucune gestion du port déjà occupé`.
- function `AsyncEventBus.start_server` — choix_technique 5/10 : `agi_core/bus.py:32: limite implicite du lecteur pour les gros messages`.
- function `AsyncEventBus.start_server` — architecture 6/10 : `agi_core/bus.py:9: port fixé séparément de la copie côté bridge`.
- function `AsyncEventBus.start_server` — tests 2/10 : `agi_core/bus.py:20: aucun test de reconnexion IPC ajouté dans ce cycle`.
- function `AsyncEventBus.start_server` — observabilite 5/10 : `agi_core/bus.py:23: journal de démarrage sans identifiant de requête`.
- function `AsyncEventBus.start_server` — securite 3/10 : `agi_core/bus.py:22: TCP local sans authentification des processus clients`.
- function `AsyncEventBus.start_server` — lisibilite 6/10 : `agi_core/bus.py:9: configuration du transport disséminée`.
- function `AsyncEventBus.subscribe` — justesse 6/10 : `agi_core/bus.py:77: event_pattern ne prend en charge qu’une égalité exacte`.
- function `AsyncEventBus.subscribe` — robustesse 4/10 : `agi_core/bus.py:79: abonnements dupliqués non évités`.
- function `AsyncEventBus.subscribe` — choix_technique 5/10 : `agi_core/bus.py:79: aucune désinscription ni durée de vie`.
- function `AsyncEventBus.subscribe` — architecture 6/10 : `agi_core/bus.py:77: contrat de callback non validé`.
- function `AsyncEventBus.subscribe` — tests 2/10 : `agi_core/bus.py:75: absence de tests d’abonnement dédiés`.
- function `AsyncEventBus.subscribe` — observabilite 5/10 : `agi_core/bus.py:80: seul le nom de l’événement est tracé`.
- function `AsyncEventBus.subscribe` — securite 3/10 : `agi_core/bus.py:79: tout callback enregistré reçoit la charge globale`.
- function `AsyncEventBus.subscribe` — lisibilite 6/10 : `agi_core/bus.py:75: nom pattern ambigu par rapport au comportement`.
- function `LLMGateway.generate_stream` — justesse 5/10 : `agi_core/llm_gateway.py:72: fin de flux acceptée sans événement done`.
- function `LLMGateway.generate_stream` — robustesse 3/10 : `agi_core/llm_gateway.py:70: JSON malformé ignoré sans diagnostic`.
- function `LLMGateway.generate_stream` — choix_technique 4/10 : `agi_core/llm_gateway.py:12: modèle par défaut absent de l’inventaire local`.
- function `LLMGateway.generate_stream` — architecture 6/10 : `agi_core/llm_gateway.py:52: contexte et température fixés dans la passerelle`.
- function `LLMGateway.generate_stream` — tests 2/10 : `agi_core/llm_gateway.py:43: qualité d’inférence non mesurée ici`.
- function `LLMGateway.generate_stream` — observabilite 3/10 : `agi_core/llm_gateway.py:76: exception renvoyée sans log corrélé`.
- function `LLMGateway.generate_stream` — lisibilite 6/10 : `agi_core/llm_gateway.py:74: erreurs encodées dans une chaîne de réponse`.
- function `LLMGateway.generate` — justesse 5/10 : `agi_core/llm_gateway.py:38: erreur HTTP transformée en texte de résultat`.
- function `LLMGateway.generate` — robustesse 3/10 : `agi_core/llm_gateway.py:31: timeout total fixe et aucune reprise qualifiée`.
- function `LLMGateway.generate` — choix_technique 4/10 : `agi_core/llm_gateway.py:12: modèle par défaut mistral absent de l’inventaire Ollama`.
- function `LLMGateway.generate` — architecture 6/10 : `agi_core/llm_gateway.py:23: contexte codé en dur indépendamment du routage`.
- function `LLMGateway.generate` — tests 2/10 : `agi_core/llm_gateway.py:14: aucun benchmark de qualité réel exécuté dans ce cycle`.
- function `LLMGateway.generate` — observabilite 4/10 : `agi_core/llm_gateway.py:37: log sans identifiant de mission`.
- function `LLMGateway.generate` — lisibilite 6/10 : `agi_core/llm_gateway.py:38: succès et erreur partagent le même type`.
- function `SwarmSupervisor.run_mission` — justesse 5/10 : `agi_core/swarm.py:69: plan dit validé sans exécution de vérification`.
- function `SwarmSupervisor.run_mission` — robustesse 4/10 : `agi_core/swarm.py:48: retour d’erreur du LLM seulement journalisé, pipeline poursuivi`.
- function `SwarmSupervisor.run_mission` — choix_technique 4/10 : `agi_core/swarm.py:52: choix du plan par texte libre sans critère objectif`.
- function `SwarmSupervisor.run_mission` — architecture 6/10 : `agi_core/swarm.py:69: planification distincte du pipeline conversation TypeScript`.
- function `SwarmSupervisor.run_mission` — tests 5/10 : `agi_core/swarm.py:79: tests de concurrence réels, génération et outils remplacés dans le test`.
- function `SwarmSupervisor.run_mission` — observabilite 5/10 : `agi_core/swarm.py:61: sorties de planification mélangées au flux final`.
- function `SwarmSupervisor.run_mission` — securite 4/10 : `agi_core/swarm.py:76: permissions relayées mais non appliquées par l’agent appelé`.
- function `SwarmSupervisor.run_mission` — lisibilite 6/10 : `agi_core/swarm.py:35: chaîne de prompts sans contrat de plan versionné`.
- function `load` — justesse 6/10 : `../aurora-remote-cli/aurora_cli/config.py:43: config corrompue remplacée silencieusement par des valeurs vides`.
- function `load` — robustesse 3/10 : `../aurora-remote-cli/aurora_cli/config.py:43: toutes les exceptions absorbées`.
- function `load` — choix_technique 5/10 : `../aurora-remote-cli/aurora_cli/config.py:41: fusion de dictionnaires sans validation de schéma`.
- function `load` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/config.py:38: lecture crée aussi des répertoires`.
- function `load` — tests 6/10 : `../aurora-remote-cli/aurora_cli/config.py:37: scénarios URL testés, corruption non testée ici`.
- function `load` — observabilite 2/10 : `../aurora-remote-cli/aurora_cli/config.py:43: aucune trace de corruption`.
- function `load` — securite 3/10 : `../aurora-remote-cli/aurora_cli/config.py:41: lecture de clé locale sans vérification des permissions du fichier`.
- function `load` — lisibilite 6/10 : `../aurora-remote-cli/aurora_cli/config.py:43: erreur non distinguée d’une configuration absente`.
- function `AuroraClient.delete` — justesse 6/10 : `../aurora-remote-cli/aurora_cli/client.py:61: réponse 204 sans JSON provoque une erreur`.
- function `AuroraClient.delete` — robustesse 4/10 : `../aurora-remote-cli/aurora_cli/client.py:61: réponse non JSON non gérée`.
- function `AuroraClient.delete` — choix_technique 6/10 : `../aurora-remote-cli/aurora_cli/client.py:59: HTTP existant adapté mais contrat de résultat absent`.
- function `AuroraClient.delete` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/client.py:63: errors réseau et réponses métier confondus`.
- function `AuroraClient.delete` — tests 3/10 : `../aurora-remote-cli/aurora_cli/client.py:57: aucun test de suppression simulée dans ce cycle`.
- function `AuroraClient.delete` — observabilite 4/10 : `../aurora-remote-cli/aurora_cli/client.py:63: aucune trace de requête corrélée`.
- function `AuroraClient.delete` — securite 5/10 : `../aurora-remote-cli/aurora_cli/client.py:28: redirections activées sans politique explicite de serveur`.
- function `AuroraClient.get` — justesse 6/10 : `../aurora-remote-cli/aurora_cli/client.py:41: JSON supposé être un objet`.
- function `AuroraClient.get` — robustesse 4/10 : `../aurora-remote-cli/aurora_cli/client.py:41: réponse HTML ou JSON invalide non gérée`.
- function `AuroraClient.get` — choix_technique 6/10 : `../aurora-remote-cli/aurora_cli/client.py:22: httpx avec reprise de connexion mais aucun contrat de réponse`.
- function `AuroraClient.get` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/client.py:43: erreurs et résultats métier partagent un dictionnaire libre`.
- function `AuroraClient.get` — tests 4/10 : `../aurora-remote-cli/aurora_cli/client.py:37: cas de réponse malformée non testé dans ce cycle`.
- function `AuroraClient.get` — observabilite 4/10 : `../aurora-remote-cli/aurora_cli/client.py:43: erreur sans identifiant de requête`.
- function `AuroraClient.get` — securite 5/10 : `../aurora-remote-cli/aurora_cli/client.py:28: redirections activées sans politique explicite de serveur`.
- function `AuroraClient.post` — justesse 6/10 : `../aurora-remote-cli/aurora_cli/client.py:51: JSON supposé être un objet`.
- function `AuroraClient.post` — robustesse 4/10 : `../aurora-remote-cli/aurora_cli/client.py:51: réponse non JSON non gérée`.
- function `AuroraClient.post` — choix_technique 6/10 : `../aurora-remote-cli/aurora_cli/client.py:49: sérialisation HTTP partagée, schéma absent`.
- function `AuroraClient.post` — architecture 6/10 : `../aurora-remote-cli/aurora_cli/client.py:53: erreurs de transport dans le même type que le résultat`.
- function `AuroraClient.post` — tests 4/10 : `../aurora-remote-cli/aurora_cli/client.py:47: erreurs de démarrage non couvertes dans ce cycle`.
- function `AuroraClient.post` — observabilite 4/10 : `../aurora-remote-cli/aurora_cli/client.py:53: absence de trace de requête corrélée`.
- function `AuroraClient.post` — securite 5/10 : `../aurora-remote-cli/aurora_cli/client.py:28: redirections activées sans politique explicite de serveur`.
- file `aurora_cli.py` — robustesse 5/10 : `aurora_cli.py:18: toute erreur d’import est présentée comme dépôt absent`.
- file `aurora_cli.py` — choix_technique 6/10 : `aurora_cli.py:11: dépendance à un dépôt frère de nom fixe`.
- file `aurora_cli.py` — observabilite 5/10 : `aurora_cli.py:19: message d’import sans cause détaillée`.
- file `aurora_cli.py` — securite 5/10 : `aurora_cli.py:24: clé persistée éventuellement issue d’un autre serveur`.
- function `main` — robustesse 5/10 : `aurora_cli.py:18: toute erreur d’import est présentée comme dépôt absent`.
- function `main` — choix_technique 6/10 : `aurora_cli.py:11: dépendance à un dépôt frère de nom fixe`.
- function `main` — observabilite 5/10 : `aurora_cli.py:19: message d’import sans cause détaillée`.
- function `main` — securite 5/10 : `aurora_cli.py:24: clé persistée éventuellement issue d’un autre serveur`.
- function `is_configured` — robustesse 6/10 : `../aurora-remote-cli/aurora_cli/config.py:70: vérifie la présence, pas la validité du couple URL/clé`.
- function `is_configured` — observabilite 5/10 : `../aurora-remote-cli/aurora_cli/config.py:70: booléen sans raison du refus`.
- function `is_configured` — securite 6/10 : `../aurora-remote-cli/aurora_cli/config.py:70: clé possiblement issue d’un autre serveur non détectée`.
