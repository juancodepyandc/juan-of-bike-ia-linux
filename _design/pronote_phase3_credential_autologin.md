# Pronote / ENT — Phase 3 : credential auto-login + scrape adaptatif

User direction (2026-05-03) :
> faut trouver juste le moyen de scrapping différent y'a pas d'ical mais
> donc au pire il donne le mot de passe et le nom d'utilisateur et aurora
> extension va sur le site de connexion se connecte capture et analyse
> toute la page pour prendre les infos nécessaire mais donc cela necessite
> un niveau de compréhension élever

L'iCal n'est pas universellement disponible (variantes ENT, blocages
admin). Solution : Aurora-Connect prend le couple **identifiant +
mot de passe**, va automatiquement sur la page de connexion de l'ENT,
remplit le formulaire, soumet, attend l'auth, puis scrape le DOM
**sans selectors hardcodés** — via analyse LLM de la page entière.

---

## Architecture proposée

### Étape 1 — credential vault (extension popup)

**Stockage** : `chrome.storage.local` chiffré avec une **passphrase
maître** (1 par appareil, jamais transmise au bridge). Implémentation :
- AES-GCM via `window.crypto.subtle`.
- Salt généré à l'install + persisté.
- Passphrase demandée au démarrage du browser (1×/session).
- Vault format :
  ```json
  {
    "ent_pronote_lycee_voltaire": {
      "loginUrl": "https://0780015h.index-education.com/pronote/eleve.html",
      "username": "encrypted_blob",
      "password": "encrypted_blob",
      "lastUsed": 1746240000000
    }
  }
  ```
- UI popup extension : add/edit/delete entry. Jamais visible en clair
  côté Aurora frontend.

### Étape 2 — auto-fill + submit

Content script Aurora-Connect injecté dans la page de login :
- Detecte les inputs `[type=email|text|password]` + leurs labels.
- Heuristique simple : 1er input non-password = username, input password
  = password. Si plusieurs : LLM hint.
- Fill les valeurs déchiffrées localement.
- Click submit (button avec text "Connexion"|"Login"|"Se connecter"|
  "Valider" OU `[type=submit]` dans le form parent).
- Wait DOMContentLoaded + 1.5s settle pour SPAs.

### Étape 3 — verify auth

Avant scrape, confirmer auth réussie :
- Check si URL a changé (login → dashboard).
- Check absence de markers d'erreur (`.error-login`, `.alert-danger`,
  texte "identifiant incorrect").
- Check présence des `authMarkers` de l'adapter (cf. Phase 2 entAdapters).

Si fail → return `{ ok: false, reason: "auth_failed" }` au bridge,
notif user "credentials invalides ou MFA bloque".

### Étape 4 — scrape adaptatif via LLM

Au lieu de selectors hardcodés (cf. Phase 2 P2.3), pour chaque section :

1. Content script extrait le DOM textuel (pas le HTML brut, trop verbeux) :
   - `document.body.innerText` truncé à 30 KB.
   - + `outerHTML` des conteneurs qui semblent listés (UL, table, ng-repeat).
2. POST au bridge → bridge envoie au LLM Ollama (via `/api/ollama/chat`)
   avec un **prompt système exigeant** :

```
Tu reçois le contenu textuel d'une page d'un ENT scolaire (Pronote/
ÉcoleDirecte/Skolengo/...). Identifie et extrait sous forme JSON les
informations scolaires structurées :
- Si c'est un cahier de textes : extract devoirs[] avec
  {title, subject, date, description, isEval}.
- Si c'est une page notes : extract notes[] avec
  {subject, grade, scale, classAvg, date, type}.
- Si c'est l'agenda : extract evenements[] avec {title, start, end}.
- Si c'est une liste de fichiers : extract fichiers[] avec
  {filename, url, subject, chapter, date}.
- Si c'est inconnu : kind: "unknown" avec brief description.

Réponds UNIQUEMENT en JSON strict.
```

3. Bridge parse la réponse, sanitize, et la persiste via le pipeline
   existant `/api/ent/harvest` (Phase 2 P2.2).

### Étape 5 — gestion erreurs robuste

- Anti-bot / CAPTCHA : si page contient h-captcha, recaptcha, ou input
  type="text" avec name="captcha" → notif "CAPTCHA détecté, complète
  manuellement".
- 2FA / MFA : si page demande code SMS/email, idem.
- Session timeout : re-login auto si sentinel "session expirée" détecté.

---

## Sécurité & légal

**Conditions explicites avant activation** :

1. **Disclaimer** : "Cette fonction stocke ton identifiant et mot de passe
   dans le navigateur, chiffré avec ta passphrase. Ils ne quittent JAMAIS
   ton appareil. Aurora ne les voit pas."
2. **Opt-in seul** : checkbox "Je comprends et accepte" dans le popup
   extension. Pas activé par défaut.
3. **Respect ToS** : noter dans le disclaimer que certains ENT
   interdisent les bots dans leurs CGU. L'user prend la responsabilité.
4. **Pas de partage** : aucune télémétrie sur les credentials.
5. **Effacement facile** : bouton "Oublier toutes les infos" dans le
   popup.

---

## Fichiers à créer

```
extension_chrome/
  ├── popup-credentials.html    NEW — UI add/edit/delete vault entries
  ├── popup-credentials.js      NEW — chrome.storage + crypto.subtle
  ├── content-autologin.js      NEW — détection inputs + fill + submit
  ├── content-scrape.js         NEW — DOM extraction + POST harvest
  └── service-worker.js         MOD — orchestre les content scripts

application/src/services/
  ├── entCredentialBridge.ts    NEW — facade typed POST → extension
  │                                (envoie ordre "auto-login + scrape ENT X")
  └── entGenericExtractor.ts    NEW — LLM-based DOM analysis bridge call

application/src/components/
  └── EntCredentialPanel.tsx    NEW — dialog Settings pour expliquer +
                                lien vers popup extension
```

---

## Estimation

- Vault popup : 2 jours.
- Auto-fill + submit : 1-2 jours (tests sur Pronote/ÉcoleDirecte).
- Verify auth + erreur handling : 1 jour.
- Scrape LLM-based : 1-2 jours (prompt engineering).
- Disclaimer + UX legal : 0.5 jour.

**Total : 5-8 jours focused dev.**

Étapes 1 et 5 peuvent shipper indépendamment de 2-4 ; ils donnent déjà
de la valeur à l'user (gestion creds + scrape manuel one-page).

---

## Phase 2.5 (cette passe v82jn) — fondation

Avant Phase 3 :
- ✅ Bridge `_EXT_LAST_SEEN` persist 24h (était 5min) — fix
  "extension disparaît".
- ✅ Endpoint `/api/cowork/extension/status` distingue active/persisted.
- ✅ ExtensionStatusPanel UI montre "actif maintenant" vs "vue il y a Xh,
  en attente" → user comprend ce qui se passe.

Phase 3 démarrera quand l'user dira "go Phase 3".
