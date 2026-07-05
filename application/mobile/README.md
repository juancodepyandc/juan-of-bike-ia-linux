# Aurora Mobile Bridge — iOS Shortcuts + Android Tasker

Ce dossier contient les **templates importables** pour relier ton iPhone/Android au bridge Aurora local. Une fois importes :

- Tu lances un raccourci sur ton telephone
- Le raccourci POST sur `https://<ton-tunnel>.trycloudflare.com/api/cowork/mobile/inbound`
- Aurora le voit et peut reagir

Et inversement, Aurora peut pousser des commandes au telephone (envoyer un SMS, lancer une lecture, etc.) via la file `/api/cowork/mobile/poll` que ton raccourci poll.

## Pre-requis

1. Ton instance Aurora doit etre joignable depuis ton telephone (typiquement via cloudflared : `https://*.trycloudflare.com`).
2. Recupere l URL de ton tunnel : commande `start-aurora.bat` affiche l URL au boot, ou regarde dans `application/bridge_server.py` les logs.
3. Note ton `extId` (un identifiant unique par telephone) — un UUID generere fait l affaire.

## Endpoints exposes par le bridge Aurora

| Endpoint | Methode | Direction | Usage |
|---|---|---|---|
| `/api/cowork/mobile/inbound` | POST | Tel → Aurora | Tel pousse un evt (transcription vocale, capteur, etc.) |
| `/api/cowork/mobile/events` | GET | Aurora → tel | Aurora liste les evts entrants (debug) |
| `/api/cowork/mobile/dispatch` | POST | Aurora → tel | Aurora pousse une commande au tel |
| `/api/cowork/mobile/poll` | GET | Tel → Aurora | Tel poll en long-poll (~25s) |
| `/api/cowork/mobile/result` | POST | Tel → Aurora | Tel envoie le resultat de la commande |

## iOS Shortcuts

Le fichier [`aurora-ios-shortcuts.json`](aurora-ios-shortcuts.json) contient 4 raccourcis prets a importer :

1. **Aurora → Send selection** — Partage un texte selectionne (Safari, Notes, n importe ou) directement vers Aurora.
2. **Aurora → Voice command** — Lance une dictee, transcrit, envoie a Aurora, lit la reponse a voix haute.
3. **Aurora → Poll commands** — Boucle de poll, execute les actions Aurora envoie (SMS, ouverture URL, lecture).
4. **Aurora → Get last response** — Recupere le dernier evt depuis `/api/cowork/mobile/events`.

### Comment importer

1. Telecharge le fichier `aurora-ios-shortcuts.json` sur ton iPhone (AirDrop, mail, iCloud Drive).
2. Ouvre le dans **Raccourcis** (l app Apple).
3. Confirme le import — l app va te demander de remplir l URL du bridge.
4. Pour le **poll loop** : ajoute le raccourci en **Automation** → "Au depart de l app Aurora" ou en **Widget**.

> ⚠️ iOS limite l execution background : le poll loop ne peut pas tourner H24. Solution : declenche-le manuellement via Siri ("Hey Siri, Aurora poll"), ou via une **Personal Automation** sur "App Opened: Raccourcis".

## Android Tasker

Le fichier [`aurora-android-tasker.xml`](aurora-android-tasker.xml) contient 3 taches Tasker :

1. **Aurora_Inbound** — Pousse une string vers `/api/cowork/mobile/inbound`.
2. **Aurora_Poll** — Boucle de poll qui declenche d autres taches Tasker quand Aurora envoie une commande (`send_sms`, `open_url`, `notify`, etc.).
3. **Aurora_Voice** — Capture vocale → transcription Google → envoi → lecture TTS de la reponse.

### Comment importer

1. Installe **Tasker** (https://tasker.joaoapps.com/) — ~3.5 EUR sur Google Play, mais c est l outil le plus puissant pour automatiser Android.
2. Telecharge `aurora-android-tasker.xml` sur ton Android.
3. Dans Tasker : 3-points menu → **Data** → **Restore** → choisis le fichier XML.
4. Edite la variable globale `%AURORA_BRIDGE_URL` avec l URL de ton tunnel.
5. Active le **Profile** "Aurora_Poll_OnUnlock" pour que le poll demarre quand tu deverrouilles.

### Variables globales a configurer

| Variable | Valeur |
|---|---|
| `%AURORA_BRIDGE_URL` | `https://<ton-tunnel>.trycloudflare.com` |
| `%AURORA_EXT_ID` | un UUID unique par appareil |

### Permissions Tasker requises

- **Send SMS** : pour `send_sms`
- **Make Phone Calls** : pour `make_call`
- **Microphone** : pour `Aurora_Voice`
- **Internet** : pour les POST/GET

## Cas d usage concrets

### Vocal : tu dictes une question, Aurora repond a voix haute

1. "Hey Siri, Aurora demande" / Tasker reconnait le geste
2. STT mobile transcrit
3. POST `/api/cowork/mobile/inbound` `{kind: "voice", text: "..."}`
4. Aurora prend le relais, repond
5. Aurora POST `/api/cowork/mobile/dispatch` `{kind: "speak", text: "..."}`
6. Le tel poll, recoit, lit a voix haute

### Aurora envoie un SMS pour toi

1. Tu demandes a Aurora "envoie un SMS a maman pour dire que je suis en chemin"
2. Aurora POST `/api/cowork/mobile/dispatch` `{kind: "send_sms", to: "+33...", body: "..."}`
3. Le tel poll, voit la commande, envoie le SMS via Tasker (ou iOS Shortcuts)
4. Tel POST `/api/cowork/mobile/result` `{ok: true, messageId: "..."}`

### Tu envoies un texte selectionne dans Safari

1. Selectionne du texte dans Safari → Share → "Aurora → Send selection"
2. Le raccourci POST sur `/api/cowork/mobile/inbound`
3. Aurora le voit dans son inbound feed et peut l analyser

## Securite

- Le bridge n a aucune protection d auth par defaut sur ces routes. **Ne les expose pas sur Internet sans tunnel chiffre + IP allowlist.**
- Le tunnel cloudflared change d URL a chaque redemarrage — pense a mettre a jour ta variable Tasker / Shortcuts.
- Pour usage permanent : configure cloudflared avec un domaine fixe + auth Cloudflare Access.

## Debug

- Verifie le bridge : `curl https://<tunnel>/api/cowork/mobile/events` doit renvoyer `{ok:true, events:[]}`.
- Trace tes POST : ajoute `set log` dans Tasker.
- Sur iOS Shortcuts : utilise l action **Show Result** pour voir le payload renvoye par Aurora.
