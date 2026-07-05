# Aurora-Mobile-Bridge — déclencher le téléphone depuis AuroraIA

Permet à Aurora de demander à ton iPhone (Shortcuts) ou ton Android (Tasker / Macrodroid) d'exécuter des actions natives — envoyer SMS, lancer un appel, ouvrir une app, prendre une photo, supprimer une photo, allumer une LED Hue, etc.

## Architecture

```
AuroraIA (PC ou tunnel) ──push──► Bridge :3001 ──poll──► iPhone Shortcut (boucle 30s)
                                         │
                                         └─poll──► Android Tasker (HTTP Request profile)
```

Le téléphone fait du **polling HTTP** sur le bridge. Quand Aurora pousse une action, le téléphone la récupère au prochain poll (typiquement 5-30 sec) et l'exécute localement avec ses propres droits OS.

**Pas d'app native à coder, pas de notif push, pas de compte tiers**. Juste un Shortcut sur iPhone (ou un profil Tasker sur Android) qui boucle.

## Endpoints bridge

| Route | Direction | Effet |
|---|---|---|
| `POST /api/aurora-mobile/push` | Aurora → bridge | Aurora ajoute une action `{platform, action, args}` |
| `GET /api/aurora-mobile/poll/{ios\|android}` | Téléphone → bridge | Le téléphone récupère et vide la queue |
| `POST /api/aurora-mobile/result` | Téléphone → bridge | Le téléphone renvoie un résultat |
| `GET /api/aurora-mobile/result/{id}` | Aurora → bridge | Aurora récupère le résultat |
| `GET /api/aurora-mobile/status` | — | Diagnostic (token requis ? combien d'actions en attente) |

**Auth**: variable d'environnement `AURORA_MOBILE_TOKEN` côté bridge. Si elle est vide → endpoints ouverts (dev local). Si elle est définie → header `X-Aurora-Token` ou `?token=xxx` requis sur tous les appels.

## Format d'une action

```json
{
  "platform": "ios",
  "action": "sms",
  "args": { "to": "+33612345678", "body": "Test depuis Aurora" },
  "shortcut_name": "Aurora Trigger"
}
```

`action` peut être: `sms`, `email`, `call`, `open_app`, `custom`. `args` est libre — c'est ton Shortcut/Tasker qui interprète.

## Setup iPhone (iOS Shortcuts)

1. **Ouvre l'app Raccourcis** → bouton `+` en haut à droite.
2. **Renomme** le shortcut: `Aurora Trigger`.
3. Construis ces actions dans cet ordre (toutes dispo dans la galerie d'actions):

   1. **Get Contents of URL**
      - URL: `http://<IP-LOCALE-DU-PC>:3001/api/aurora-mobile/poll/ios?token=<TON-TOKEN>` (ou utilise le tunnel `https://xxx.trycloudflare.com/...` si tu n'es pas sur le même réseau)
      - Method: GET
      - (Headers — optionnel: `X-Aurora-Token` à la place du `?token=`)

   2. **Get Dictionary from Input** (parse le JSON)

   3. **Get Dictionary Value** → `commands` (array)

   4. **Repeat with Each** (boucle sur les commandes)
      - Dans la boucle:
        - **Get Dictionary Value** → `action` sur l'item courant → variable `action`
        - **Get Dictionary Value** → `args` sur l'item courant → variable `args`
        - **If** `action` is `sms`:
          - **Get Dictionary Value** → `to` puis `body` sur `args`
          - **Send Message** avec `body` à `to`
        - **Otherwise If** `action` is `call`:
          - **Get Dictionary Value** → `to` sur `args`
          - **Call** `to`
        - **Otherwise If** `action` is `email`:
          - **Get Dictionary Value** → `to`, `subject`, `body` sur `args`
          - **Send Email** avec ces champs
        - **Otherwise If** `action` is `open_app`:
          - **Get Dictionary Value** → `bundle_id` sur `args`
          - **Open App** par bundle ID
        - **Otherwise** (custom):
          - Exécute ce que tu veux selon `args` (afficher une notif, lancer une URL, etc.)
        - **(optionnel) Get Contents of URL** vers `/api/aurora-mobile/result` avec body `{id, ok:true, output:"done"}` pour fermer la boucle.

4. **Automatisation**: dans l'onglet Automatisation, crée une "Personal Automation":
   - Trigger: "Time of Day" → toutes les 30 minutes (ou plus court avec un workaround NFC tag).
   - Action: Run Shortcut → `Aurora Trigger`.
   - **Décoche "Ask Before Running"** pour exécution silencieuse.

   Limitation iOS: pas de poll < 30 min sans tag NFC ou hack. Pour du quasi-temps-réel, pose un tag NFC sur ton bureau et configure-le sur `Aurora Trigger`. Tape le tag avec le téléphone à chaque fois que tu veux que Aurora prenne la main.

5. **Test** depuis Aurora:
   ```bash
   curl -X POST http://127.0.0.1:3001/api/aurora-mobile/push \
        -H "Content-Type: application/json" \
        -d '{"platform":"ios","action":"sms","args":{"to":"+33XXX","body":"Hello from Aurora"}}'
   ```
   Tape le NFC tag (ou attends le timer) → ton iPhone exécute Send Message.

## Setup Android (Tasker — recommandé)

Tasker permet du polling court (5s minimum), il est plus puissant que Shortcuts.

1. **Installe Tasker** ([Play Store](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm), payant ~3€).
2. Onglet **Profils** → `+` → **Time** → toutes les 1 min (ou less avec State trigger).
3. **Task associée** → `Aurora Poll`:
   - **HTTP Request** (action HTTP):
     - Method: GET
     - URL: `http://<IP-PC>:3001/api/aurora-mobile/poll/android`
     - Headers: `X-Aurora-Token: <TON-TOKEN>`
     - Output Variable: `%commands`
   - **JavaScriptlet**:
     ```javascript
     var data = JSON.parse(commands);
     for (var i=0; i<data.commands.length; i++) {
       var cmd = data.commands[i];
       setLocal('cmd_id_'+i, cmd.id);
       setLocal('cmd_action_'+i, cmd.action);
       setLocal('cmd_args_'+i, JSON.stringify(cmd.args));
     }
     setLocal('cmd_count', data.commands.length);
     ```
   - **For** loop sur `%cmd_count`:
     - **If** `%cmd_action` ~ `sms`:
       - **Send SMS** → `%cmd_args` parsed via JavaScriptlet.
     - **If** `%cmd_action` ~ `call`:
       - **Call** → `to` extrait des args.
     - **If** `%cmd_action` ~ `open_app`:
       - **Launch App** → bundle id.
     - **If** `%cmd_action` ~ `custom`:
       - **Run Shell** ou n'importe quelle action Tasker (Bluetooth toggle, WiFi, brightness, etc.).

4. **ADB optionnel** (pour automations avancées sans root):
   - Active "USB debugging over WiFi" sur ton Android.
   - Sur le PC: `adb connect <IP-ANDROID>:5555` puis `adb shell <commande>`.
   - Aurora peut alors exécuter `adb shell am start -n com.app/.Activity` directement via `run_command` (capability shell, mode Tauri).

## Setup Android (Macrodroid — alternative gratuite)

Macrodroid est gratuit et plus simple que Tasker. Configuration similaire:

1. **Macro** → **Trigger**: Timer (1 min)
2. **Action**: HTTP Request → ton bridge poll
3. **Action**: Parse JSON → variables locales
4. **Action**: Switch sur `cmd_action` → SMS / Call / Open App / etc.

## Exemples d'usage côté Aurora

Tu tapes dans le module Cowork:
- *"envoie un SMS à Léa pour dire que je suis en retard"* → Aurora produit `{ kind: 'mobile_trigger', platform: 'ios', action: 'sms', args: { to: 'Lea', body: 'Suis en retard' } }`
- *"appelle le médecin"* → `mobile_trigger / call`
- *"ouvre Spotify"* → `mobile_trigger / open_app` avec bundle_id `com.spotify.music`
- *"prends une photo"* → action `custom` avec args dispatchés vers Camera in Tasker / Shortcut.

## Sécurité

- **Toujours configurer `AURORA_MOBILE_TOKEN`** en production (variable d'env du bridge). Sans token, n'importe qui sur le réseau peut envoyer des actions.
- Les actions destructives (sms, call, mail) demandent confirmation dans le CoworkOverlay AVANT push vers le téléphone.
- Le téléphone exécute UNIQUEMENT ce qu'il a programmé dans son Shortcut/Tasker — Aurora ne peut pas dépasser ce périmètre.
- Pas de credentials téléphoniques côté bridge — tout reste dans Shortcuts / Tasker.

## Limitations connues

- **iOS Shortcuts**: polling minimum 30 min via Personal Automation sans NFC tag. Workaround: utiliser un tag NFC ou un Apple Watch face complication custom.
- **iOS Send Message**: nécessite confirmation utilisateur sur les versions récentes (iOS 17+).
- **Android Tasker**: minimum 1 min, plus court possible avec un trigger State (notif, charge, etc.).
- **Pas de result push** depuis le téléphone — c'est l'iPhone/Android qui POSTe le résultat à la fin de chaque action s'il est configuré.

## Roadmap

- [x] Bridge endpoints push/poll/result avec auth token
- [x] Action `mobile_trigger` dans le pipeline Cowork
- [x] Documentation Shortcuts + Tasker
- [ ] Templates Shortcut .shortcuts importables
- [ ] Profil Tasker .prj.xml importable
- [ ] App native iOS lite avec polling 5s background (App Store TestFlight)
- [ ] Server-Sent Events au lieu de polling pour latence < 1s
