# Aurora-Connect - installation navigateur

Aurora-Connect relie AuroraIA, qui tourne sur ton PC, a tes onglets navigateur. Elle permet a Aurora de lire une page, cliquer, remplir un formulaire, lancer un scrape et renvoyer les resultats au bridge local.

Cette extension donne a Aurora un acces large aux pages ou elle est active. Installe-la seulement sur une machine et un navigateur que tu controles.

## Telechargement

Dans Aurora, ouvre **Cowork > Parametres > Connecteurs > Aurora-Connect**, puis clique sur **Telecharger l extension**. Le bridge cree un ZIP frais depuis `application/extension/`.

URL directe quand Aurora tourne : `http://127.0.0.1:3001/api/cowork/extension/download`

Decompresse le ZIP dans un dossier permanent, par exemple `%LOCALAPPDATA%\aurora-connect\` sur Windows.

## Chrome, Edge, Brave, Opera, Vivaldi

1. Ouvre la page des extensions de ton navigateur :
   - Chrome : `chrome://extensions`
   - Edge : `edge://extensions`
   - Brave : `brave://extensions`
   - Opera : `opera://extensions`
   - Vivaldi : `vivaldi://extensions`
2. Active le mode developpeur.
3. Clique sur **Charger l extension non empaquetee** ou **Load unpacked**.
4. Selectionne le dossier extrait.
5. Clique sur l icone Aurora-Connect et verifie que le bridge pointe vers `http://127.0.0.1:3001` ou vers ton tunnel actif.

## Firefox

Firefox n accepte les extensions non signees que temporairement.

1. Ouvre `about:debugging#/runtime/this-firefox`.
2. Clique sur **Load Temporary Add-on**.
3. Selectionne le `manifest.json` du dossier extrait.

L extension sera retiree au prochain redemarrage de Firefox.

## Verification

1. Clique sur l icone Aurora-Connect.
2. Le statut doit indiquer que le bridge est connecte.
3. Dans Cowork, demande : `lis le titre de la page courante`.
4. Aurora doit lire l onglet actif et repondre avec le titre observe.

## Credentials ENT / Pronote

Pour Pronote ou un ENT :

1. Ouvre le popup Aurora-Connect, puis la zone credentials.
2. Deverrouille ou cree le vault chiffre.
3. Dans Aurora, va dans les parametres Cowork et ajoute ton etablissement, ton identifiant et ton mot de passe.
4. Aurora enregistre ces donnees dans le vault de l extension, puis peut lancer auto-login + scrape des devoirs, notes, fichiers et agenda.

Si un CAPTCHA, un code MFA ou une validation parentale apparait, Aurora s arrete et te laisse le finir manuellement.

## Permissions

- `activeTab` et `scripting` : lire et agir sur l onglet actif.
- `tabs` : lister les onglets et naviguer quand Cowork le demande.
- `storage` : garder l URL du bridge, le statut et le vault chiffre.
- `contextMenus` : envoyer une selection de texte a Aurora.
- `notifications` : afficher les retours courts de l extension.
- `<all_urls>` : fonctionner sur les ENT, Pronote et les autres sites que tu veux analyser.

## Option eval

Le popup contient un toggle pour autoriser `eval` dans la page. Laisse-le coupe par defaut. Active-le seulement quand tu veux qu Aurora execute volontairement du JavaScript dans une page que tu controles.

## Desinstallation

Retourne sur la page des extensions, ouvre Aurora-Connect, puis clique sur **Remove** ou **Supprimer**.
