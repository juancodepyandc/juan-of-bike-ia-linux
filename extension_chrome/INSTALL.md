# Aurora-Connect — installation par navigateur

L extension Aurora-Connect est le pont entre AuroraIA (en local sur ton PC) et tes onglets navigateur. Elle permet a Aurora de **lire**, **cliquer**, **remplir des formulaires**, et **executer du JS** dans n importe quelle page web — sur n importe quel onglet.

> ⚠️ Cette extension donne a Aurora un acces complet aux pages que tu visites. Active la seulement si tu lui fais confiance.

---

## Telechargement

Lance Aurora puis ouvre **Cowork → Parametres → Connecteurs → Aurora-Connect** : un bouton « Telecharger l extension » te servira un ZIP frais (`aurora-connect.zip`) genere par le bridge depuis `application/extension/`. Decompresse-le dans un dossier permanent (par ex. `~/aurora-connect/` ou `%LOCALAPPDATA%\aurora-connect\` sur Windows).

URL directe (si Aurora tourne) : `http://127.0.0.1:3001/api/cowork/extension/download`

---

## Chrome / Chromium

1. Decompresse le ZIP dans un dossier permanent.
2. Ouvre `chrome://extensions` (colle dans la barre d adresse).
3. Active **Mode developpeur** (toggle en haut a droite).
4. Clique **Charger l extension non empaquetee**.
5. Selectionne le dossier extrait.
6. L icone violet « Aurora-Connect » apparait dans la barre d outils. Clique dessus, verifie que l URL du bridge pointe sur ton instance (`http://127.0.0.1:3001` ou ton tunnel `https://*.trycloudflare.com`).

## Microsoft Edge

1. Decompresse le ZIP.
2. Ouvre `edge://extensions`.
3. Active **Developer mode** (toggle a gauche).
4. Clique **Load unpacked** et pointe vers le dossier extrait.

## Brave

Identique a Chrome — Brave est un fork de Chromium.

1. `brave://extensions`
2. Mode developpeur ON
3. Charger non empaquetee → dossier extrait

## Opera

1. `opera://extensions`
2. Active **Developer mode** (en haut a droite).
3. Clique **Load unpacked extension**.

## Vivaldi

1. `vivaldi://extensions`
2. Active **Developer mode**.
3. Charger non empaquetee.

## Arc

1. **Settings → Extensions**.
2. **Manage extensions** → tu arrives sur la page Chromium.
3. Mode developpeur ON → Charger non empaquetee.

## Firefox

⚠️ Firefox demande une signature pour les installations permanentes. Pour les essais en local :

1. Decompresse le ZIP.
2. Ouvre `about:debugging#/runtime/this-firefox`.
3. Clique **Load Temporary Add-on…**.
4. Selectionne le `manifest.json` du dossier extrait.

L extension reste active jusqu au prochain redemarrage de Firefox. Pour permanent, soumets sur [addons.mozilla.org](https://addons.mozilla.org/developers/).

## Safari (macOS)

⚠️ Safari requiert un wrapper Xcode pour les extensions Web. Steps :

1. Lance **Xcode** (gratuit sur le Mac App Store).
2. **File → New → Project → Safari Extension App**.
3. Donne lui un nom (ex. `AuroraConnect`).
4. Dans le projet genere, ouvre `<AppName> Extension/Resources/` et remplace son contenu par les fichiers du ZIP Aurora-Connect (`manifest.json`, `background.js`, `content.js`, `popup.html`, etc.).
5. Build & Run (Cmd+R).
6. Dans Safari : **Preferences → Extensions** — active Aurora-Connect.
7. **Safari → Settings → Advanced** : coche **Show Develop menu**, puis **Develop → Allow Unsigned Extensions** chaque session.

---

## Verification

Apres installation :

1. Clique sur l icone Aurora-Connect dans la barre d extensions.
2. Tu dois voir une pastille verte « Connecte au bridge ».
3. Sur AuroraIA, ouvre **Cowork** et tape : `lis le titre de la page courante`.
4. Aurora devrait emettre un appel `dom_query` qui ressort le titre.

## Permissions detaillees

L extension demande :

- `activeTab` + `scripting` — lire/modifier le DOM de l onglet actif.
- `tabs` — lister/changer d onglet (utilise par `list_tabs`/`navigate`).
- `storage` — sauvegarder ton URL de bridge + les toggles.
- `contextMenus` — ajouter « Envoyer la selection a Aurora ».
- `notifications` — afficher le toast quand une selection est envoyee.
- `<all_urls>` — pour fonctionner sur n importe quelle page.

Tu peux desactiver l acces a un site donne via le bouton extension → **Manage extension → Site access**.

## Toggle "eval"

Le popup expose un toggle « Autoriser eval JS arbitraire ». Quand il est OFF (defaut), Aurora peut lire le DOM, cliquer, remplir — mais pas executer du JS arbitraire. Active cette case si tu veux qu Aurora puisse `eval` du code dans la page (ex. extraire des donnees calculees, automatiser une routine complexe). Garde OFF sur des sites tiers que tu ne controles pas.

## Securite

- Tous les appels passent par `http://127.0.0.1:3001` (ou le tunnel cloudflared) que TOI tu controles.
- Aucune cle d API n est jamais transmise a Anthropic, Google, ou un tiers — l extension parle uniquement a ton bridge local.
- Les actions destructives (click "Send", remplir un formulaire de paiement) restent gatees par les confirmations Cowork si trust mode est OFF.

## Desinstaller

Suis la procedure inverse — `chrome://extensions` → Aurora-Connect → Remove. Sur Firefox, l add-on temporaire disparait au redemarrage; permanent → AMO. Sur Safari, supprimer l app wrapper Xcode.
