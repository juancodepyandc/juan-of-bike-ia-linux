# Aurora-Connect — extension navigateur

> **DEPRECATED (v82l6, 2026-05).** Ce dossier est un legacy figé à la version
> `1.2.0` (Apr 2025). La source officielle, bumpée automatiquement par
> `bump-extension-version.py` et servie par `/api/cowork/extension/version`,
> est désormais **`application/extension/`**. Le bridge garde ce dossier
> en fallback uniquement pour ne pas casser un poste qui aurait installé
> l ancienne extension.
>
> N installe plus depuis ici. Suis `application/extension/INSTALL.md`.

---

Connecte ton navigateur (Chrome / Edge / Firefox / Safari) à AuroraIA pour lui permettre de:
- lire le DOM de la page courante
- cliquer sur des éléments
- remplir des champs / formulaires
- exécuter des expressions JavaScript sandboxées
- naviguer entre les onglets

L'extension communique avec le bridge AuroraIA local (par défaut `http://127.0.0.1:3001`) via du polling HTTP. Pas de WebSocket, pas de dépendance — fonctionne avec Flask de base.

## Installation (Chrome / Edge — Manifest V3)

1. Ouvre `chrome://extensions` (ou `edge://extensions`).
2. Active **Mode développeur** en haut à droite.
3. Clique **Charger l'extension non empaquetée** et sélectionne le dossier `application/aurora-connect-extension/`.
4. L'extension apparaît dans la barre. Clique l'icône Aurora-Connect pour ouvrir le popup.
5. Configure le **bridge URL** (par défaut `http://127.0.0.1:3001`) et clique **Enregistrer**.
6. Active le toggle. Le pill devient vert et l'extension commence à poller.

## Installation (Firefox — Manifest V3 supporté depuis FF 109)

1. Ouvre `about:debugging#/runtime/this-firefox`.
2. Clique **Charger un module complémentaire temporaire** et sélectionne `manifest.json`.

## Installation (Safari)

Safari nécessite de packager l'extension via Xcode (Safari Web Extensions). Voir [docs.apple.com/safari-extensions](https://developer.apple.com/documentation/safariservices/safari_web_extensions). Le code source de cette extension est compatible — seul le packaging change.

## Architecture

```
aurora-connect-extension/
├── manifest.json        # Manifest V3 declaratif
├── background.js        # Service worker — polling + dispatch
├── content.js           # Injecte dans chaque page — read DOM / click / fill / eval
├── popup.html / popup.js # UI popup avec status + config + mini-chat
├── options.html         # Page options (config bridge URL + token)
└── icons/               # Icônes 16/48/128
```

## Commandes supportées

L'extension reçoit des commandes JSON du bridge via `/api/aurora-connect/poll` et POST les résultats sur `/api/aurora-connect/result`.

| Kind | Args | Effet |
|---|---|---|
| `ping` | — | retourne `pong` + UA |
| `tabs_list` | — | liste tous les onglets ouverts |
| `navigate` | `{ url }` | navigue l'onglet actif vers l'URL |
| `read_dom` | `{ selector? }` | lit le DOM (sélecteur ou page entière) |
| `click` | `{ selector }` | clique l'élément |
| `fill` | `{ selector, value }` | remplit un input/textarea avec dispatch des events React/Vue |
| `eval` | `{ expression }` | évalue une expression JS isolée |

## Sécurité

- **Token optionnel** dans la config — envoyé en header `X-Aurora-Token` à chaque requête.
- **Polling local** uniquement (`127.0.0.1:3001`) par défaut. Ouvre les permissions vers `*.trycloudflare.com` si tu utilises un tunnel.
- **Sandboxed eval** via `new Function()` — pas d'accès au DOM via `eval` direct.

## Compatible avec

- Chrome 88+ / Edge 88+ / Firefox 109+ / Safari 16+ (avec packaging Xcode)
- AuroraIA-v2 bridge_server.py — endpoints `/api/aurora-connect/poll` et `/api/aurora-connect/result` ajoutés.

## Roadmap

- [x] Manifest V3 avec service worker, content script, popup, options
- [x] Polling HTTP pour récupérer les commandes
- [x] DOM read / click / fill / eval / navigate / tabs_list
- [x] Mini-chat dans le popup
- [ ] WebSocket pour push immédiat (étape future)
- [ ] Capture d'onglet (chrome.tabs.captureVisibleTab) pour vision IA
- [ ] Manifest V2 fallback Firefox legacy
