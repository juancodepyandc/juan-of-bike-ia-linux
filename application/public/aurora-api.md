# Aurora API — intégration site externe (chat + génération 3D)

> Doc pour le dev (ou l'IA) qui intègre Aurora dans le site **`site-rep`** (les boutons « Aperçu » sont déjà en place côté site).
> Cette API est servie par le bridge local d'Aurora (PC fixe du propriétaire) exposé via un tunnel Cloudflare.
> **Ça marche tant que le PC fixe du propriétaire est allumé** (bridge + tunnel actifs).

---

## 0. Base URL & clé

| | valeur |
|---|---|
| **Base URL** | `https://physical-thats-europe-comparable.trycloudflare.com` *(peut changer — voir §7)* |
| **Clé d'API** | fournie par le propriétaire (Aurora → Paramètres → « API · Site externe »). Format `aur_…`. Verrouillée sur le(s) domaine(s) du site. |
| **Auth** | header `Authorization: Bearer <clé>` sur chaque appel `/api/ext/*` (sauf `/api/ext/key/*` qui est local-only). |

La clé est durcie côté serveur : seul son SHA‑256 salé est stocké (jamais la clé en clair), comparaison à temps constant, **verrou de domaine** (`Access-Control-Allow-Origin` = le domaine déclaré, jamais `*` si un domaine est fixé), **rate‑limit** 40 req / 60 s par clé. ⚠️ Si tu mets la clé dans le HTML (attribut du widget), elle est visible dans le source de la page — c'est le verrou de domaine qui te protège alors. Ne mets jamais une clé **sans domaine** sur une page publique.

CORS : tous les endpoints `/api/ext/*` répondent aux préflights `OPTIONS` et renvoient les bons headers CORS pour le domaine de la clé. `/api/3d/file/*` renvoie `Access-Control-Allow-Origin: *` (fichiers GLB → librement téléchargeables).

---

## 1. Endpoints

### `POST /api/ext/do`  — **universel : envoie une demande, il route tout seul** ⭐
Le plus simple : `{ "request": "<ce que tu veux, en langage naturel>" }`. Il classe (chat / code / mesh3d / image / video / sim) et fait le bon traitement. Tu peux forcer : `{ "request":"…", "kind":"code" }`.
Réponses selon le type :
```jsonc
// chat / Q&R / conseil
{ "kind": "chat",  "model": "…", "reply": "…" }
// génération de code : sketch Arduino .ino, firmware ESP32/ESP8266 (Arduino-core ou PlatformIO),
// scripts Python/JS/Bash, configs, C/C++/Rust… → Markdown avec blocs fence-és + noms de fichiers
{ "kind": "code",  "model": "…", "result": "<markdown>", "note": "compile/flash côté toi (arduino-cli, pio, esptool…)" }
// mesh 3D → lance le pipeline (asynchrone), poll comme /api/ext/3d/status
{ "kind": "mesh3d", "job_id": "ext3d_…", "poll": "/api/ext/3d/status/ext3d_…", "note": "~20-30 min, refait auto si rejeté" }
// image / video / sim → pas (encore) via l'API
{ "kind": "image", "supported": false, "note": "utilise l'app Aurora (modules Image / Vidéo / Simulateur)" }
```
> ⚠️ Les requêtes `code` longues (gros firmware) peuvent prendre >100 s → timeout Cloudflare (524), surtout si une génération 3D tourne en même temps (un seul GPU). Découpe la demande, ou réessaie. (Pour le 3D, c'est déjà asynchrone, pas de souci.)
> **Ce que l'API ne fait PAS :** simulateur Arduino/ESP qui *exécute* le firmware sur du HW virtuel, ni construction d'une vraie image d'OS bootable. Le chemin `code` **écrit** le firmware/sketch/scripts (+ instructions de flash/build) ; l'exécution reste de ton côté (arduino-cli, PlatformIO, esptool, QEMU, Wokwi…).

### `GET /api/ext/ping`
Santé + modèle local actif.
```
→ { "ok": true, "model": "qwen3-vl:8b" }       // 200
→ { "ok": false, "error": "clé invalide" }      // 401
```

### `POST /api/ext/chat`  — conversation (texte → texte)
Body :
```jsonc
{
  "messages": [ { "role": "user", "content": "…" }, { "role": "assistant", "content": "…" }, … ],  // OU
  "prompt": "…",                 // raccourci pour un seul message user
  "model": "qwen3-vl:8b",        // optionnel
  "temperature": 0.7             // optionnel (0–1.5)
}
```
Réponse :
```jsonc
{ "reply": "…", "model": "qwen3-vl:8b" }   // 200
```
Erreurs : `401` (clé manquante/invalide), `403` (origine non autorisée), `429` (rate‑limit), `400` (body invalide), `502` (modèle injoignable).
> C'est **sans état côté serveur** : tu envoies l'historique que tu veux à chaque appel (cap interne : 20 derniers messages, 8000 chars/message).

### `POST /api/ext/3d/generate`  — génère un GLB depuis un prompt
Pipeline : synthèse d'images de référence (FLUX, multi‑vues) → reconstruction mesh (Hunyuan3D) → post‑traitement / auto‑rescue (nettoyage géométrie, couleurs). **Long : ~20–30 min.** Priorité **précision/réalisme**, pas la vitesse.
Body :
```jsonc
{ "prompt": "boîtier PC ATX noir, panneau latéral en verre, écran LCD 5\" en façade, bandeau 8 LED RGB en haut",
  "subject_kind": "pc_tower",    // optionnel — aide le router (ex: pc_tower, enclosure, screen, component…)
  "force": false }               // optionnel — relance même si un run identique existe
```
Réponse :
```jsonc
{ "ok": true, "job_id": "ext3d_…", "poll": "/api/ext/3d/status/ext3d_…" }
```

### `GET /api/ext/3d/status/<job_id>`  — suivi du job
```jsonc
{
  "job_id": "ext3d_…",
  "state": "queued" | "running" | "done" | "failed",
  "elapsed_s": 412.3,            // temps écoulé en direct
  "step": "synthèse référence → Hunyuan3D → post-traitement / rescue",
  "attempts": 1,                 // passe 2 = nouvelle passe automatique car rendu rejeté
  "score": 78,                   // score qualité 0–100 (null tant que pas évalué)
  "glb_url": "/api/3d/file/ext_…_mesh.glb",   // présent quand done (ou en best-effort si failed)
  "audit": { … }                 // audit aurora.pipeline.v1 quand done
}
```
**Auto‑rejet/refait :** si le score final est < 70, le pipeline est **relancé automatiquement** (max 2 passes). Si après 2 passes c'est toujours rejeté → `state: "failed"` (le `glb_url` du dernier essai reste exposé en best‑effort pour inspection). Donc côté site : poll toutes les ~5 s, montre `step` + `elapsed_s`, et n'affiche le résultat que sur `state: "done"`.

### `GET /api/3d/file/<nom.glb>`  — télécharge le binaire GLB
`Content-Type: model/gltf-binary`, `Access-Control-Allow-Origin: *`, cache 1 j. Path‑traversal bloqué (que des `.glb`/`.gltf` du dossier de sortie 3D). Le `glb_url` renvoyé par le status est un chemin relatif → URL finale = `<Base URL>` + `glb_url`.

### `POST /api/ext/key/{generate,revoke}`, `GET /api/ext/key/status`  — *local-only* (gestion de clé)
Réservé à l'app Aurora sur la machine du propriétaire. Pas pertinent côté site.

---

## 2. Mode A — widget de conversation (drop‑in)

Colle avant `</body>` :
```html
<script src="https://physical-thats-europe-comparable.trycloudflare.com/aurora-embed.js"
        data-aurora-url="https://physical-thats-europe-comparable.trycloudflare.com"
        data-aurora-key="aur_TA_CLÉ"
        data-aurora-title="Assistant atelier"
        data-aurora-accent="#d97757"></script>
```
→ une bulle de chat apparaît en bas à droite (équivalent du module Conversation d'Aurora).

API JS exposée (objet global `AuroraEmbed`) :
```js
AuroraEmbed.init({ url, key, title, accent })   // init manuelle (si pas via data-attrs)
AuroraEmbed.open() / AuroraEmbed.close()
AuroraEmbed.ask("ma question")                  // ouvre le panneau + envoie
AuroraEmbed.generate3D(prompt, (s) => { … })    // lance une génération 3D (cf. mode B)
```
Dans le chat, taper **`/3d <description>`** lance aussi une génération 3D.
Le widget émet sur `window` l'event **`aurora-embed:3d-ready`** quand un GLB est prêt :
```js
window.addEventListener('aurora-embed:3d-ready', (e) => {
  const { url, audit, prompt } = e.detail   // url = URL complète du .glb
  chargerDansLeViewer(url)
  persister(prompt, url)                     // cf. §4
})
```

---

## 3. Mode B — appel direct (ton propre bouton « Aperçu »)

C'est le cas du site `site-rep` (boutons « Aperçu » déjà en place). Le site **sait quel composant est sélectionné** (catalogue de noms/specs). Au clic :

```js
const BASE = 'https://physical-thats-europe-comparable.trycloudflare.com';
const KEY  = 'aur_TA_CLÉ';   // idéalement injectée côté serveur, pas en dur dans le bundle public

async function genererApercu3D(composant, onProgress) {
  // 1) construire un prompt descriptif à partir des infos du composant
  const prompt = `${composant.categorie} ${composant.nom} — ${composant.specs}`.slice(0, 600);
  // ex: "carte graphique NVIDIA RTX 4090 Founders Edition, triple ventilateur, backplate métal"
  //     "boîtier PC ATX Lian Li O11, panneau latéral verre trempé, écran LCD 5 pouces façade, 8 LED RGB"

  // 2) lancer le job
  const r = await fetch(`${BASE}/api/ext/3d/generate`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, subject_kind: composant.kind /* optionnel */ }),
  });
  const { job_id, error } = await r.json();
  if (!job_id) throw new Error(error || `HTTP ${r.status}`);

  // 3) poll
  while (true) {
    await new Promise(res => setTimeout(res, 5000));
    const s = await fetch(`${BASE}/api/ext/3d/status/${job_id}`, { headers: { 'Authorization': `Bearer ${KEY}` } }).then(x => x.json());
    onProgress?.(s);  // { state, elapsed_s, step, attempts, score }
    if (s.state === 'done')   return { glbUrl: BASE + s.glb_url, score: s.score, audit: s.audit };
    if (s.state === 'failed') throw new Error(s.error || 'rendu rejeté');
  }
}

// utilisation
genererApercu3D(composantSelectionne, (s) => {
  majBarre(`${s.step} — ${Math.round(s.elapsed_s)}s${s.attempts > 1 ? ` (passe ${s.attempts})` : ''}`);
}).then(({ glbUrl, score }) => {
  chargerDansLeViewer(glbUrl);     // affichage immédiat dans ton viewer three.js
  persister(composantSelectionne.id, glbUrl);   // §4 — pour que ce soit permanent
});
```

**Modulaire :** que ce soit le **bouton « Aperçu »** (mode B) ou la **conversation** (mode A, `/3d …`), c'est le même endpoint qui traite — il suffit que le site délivre une description correcte du composant. Tu peux mixer les deux.

**Assembler / comparer plusieurs composants :** chaque composant donne son propre `.glb`. Côté viewer : charge plusieurs GLB dans la même scène (positionne‑les), ou affiche‑les côte à côte. (L'API ne fait pas l'assemblage — elle livre les pièces ; l'assemblage/comparaison est ton job côté site.)

---

## 4. Rendre le GLB **permanent** (« à tout jamais sur le site »)

⚠️ L'URL du tunnel est **éphémère** (ne vit que tant que le PC du propriétaire est allumé, et change si le tunnel est recréé). Donc pour que le 3D reste sur le site, il faut **télécharger le `.glb` une fois et le stocker chez toi**. Vu que le site est sur **Vercel** :

**Option a — Vercel Blob (recommandé) :** une fonction serverless qui fetch le GLB et l'upload.
```js
// /api/persist-glb.js  (Vercel serverless)  — nécessite `@vercel/blob`
import { put } from '@vercel/blob';
export default async function handler(req, res) {
  const { glbUrl, componentId } = req.body;        // glbUrl = celle renvoyée par Aurora
  const buf = Buffer.from(await (await fetch(glbUrl)).arrayBuffer());
  const blob = await put(`components/${componentId}.glb`, buf, { access: 'public', contentType: 'model/gltf-binary' });
  // → enregistre blob.url dans ta base / ton catalogue de composants
  res.json({ url: blob.url });
}
```
**Option b — commit dans le repo GitHub `site-rep` :** une fonction serverless (avec un token GitHub en secret) qui `PUT` le `.glb` dans `/public/components/<id>.glb` via l'API GitHub Contents → Vercel redéploie → permanent. (Le binaire : `Buffer.from(await (await fetch(glbUrl)).arrayBuffer()).toString('base64')` pour le champ `content`.)
**Option c — cache navigateur / IndexedDB** si tu veux juste que ça reste pendant la session.

> Si tu veux qu'Aurora pousse elle‑même le `.glb` dans le repo `site-rep` (au lieu que ce soit le site qui le récupère), c'est possible — il faudrait configurer un token GitHub côté machine du propriétaire ; demande‑le et ce sera branché côté bridge.

---

## 5. Logs depuis la conversation

Le chat est **sans état côté Aurora** — c'est à toi de logger si tu veux un historique. Deux façons :

**Via le widget** — enrobe `AuroraEmbed.ask` :
```js
const _ask = AuroraEmbed.ask;
AuroraEmbed.ask = (txt) => { logChat({ ts: Date.now(), role: 'user', content: txt }); return _ask(txt); };
// (la réponse assistant arrive dans le DOM du widget ; pour la capter proprement, préfère le mode "appel direct" ci-dessous)
```
**Via l'appel direct** (le plus propre pour logger) :
```js
async function chatLogged(messages) {
  const reply = await fetch(`${BASE}/api/ext/chat`, {
    method: 'POST', headers: { 'Authorization': `Bearer ${KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  }).then(r => r.json());
  await fetch('/api/log', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ts: Date.now(), in: messages.at(-1), out: reply.reply }) });   // ton endpoint de log
  return reply.reply;
}
```
Pareil pour les générations 3D : log `{ ts, prompt, job_id, score, glbUrl, audit }` côté `/api/log`.

---

## 6. Erreurs & robustesse

| code | sens | que faire |
|---|---|---|
| `401` | clé manquante/invalide/révoquée | vérifier le header `Authorization: Bearer …` ; demander une nouvelle clé au propriétaire |
| `403` | origine non autorisée pour cette clé | la requête vient d'un domaine non déclaré dans la clé ; demander d'ajouter le domaine (la clé accepte plusieurs domaines en CSV : `https://site-rep.vercel.app, http://localhost:3000`) |
| `429` | rate‑limit (40 req / 60 s / clé) | back‑off + réessai |
| `502` | modèle / pipeline injoignable, ou réponse vide | le PC est allumé mais Ollama/Hunyuan est occupé (un seul GPU → chat lent si un job 3D tourne en même temps) ; réessayer |
| `504` | timeout pipeline (cap 40 min) | relancer ; vérifier que le pipeline 3D n'est pas bloqué côté machine |
| réseau / `502` Cloudflare sur tout | le tunnel ou le bridge est tombé | le propriétaire doit relancer (cf. §7) |

---

## 7. Si le lien du tunnel change

Le `Base URL` `*.trycloudflare.com` est régénéré si le tunnel est recréé. Stratégies pour ne pas hard‑coder :
- lire le lien courant depuis le repo Aurora : `https://raw.githubusercontent.com/juancodepyandc/juan-of-bike-ia/main/tunnel_url.txt` (le propriétaire le commit) — fetch ce fichier au chargement, en fallback sur la valeur en dur ;
- ou stocker le lien dans une variable d'env Vercel que le propriétaire met à jour ;
- le propriétaire vous prévient à chaque changement.

---

## TL;DR pour le dev du site

1. Clés (auprès du propriétaire) : une **illimitée pour les appels SERVEUR** (env var Vercel, jamais dans le bundle public — la recommandée) + une **verrouillée sur le domaine pour le widget** (`data-aurora-key`).
2. **Le plus simple = `POST /api/ext/do {request: "<n'importe quoi en langage naturel>"}`** → il route vers chat / code / mesh3d / image tout seul (§1).
3. **Bouton « Aperçu » d'un composant** → `POST /api/ext/3d/generate {prompt: "<desc du composant>"}` (ou `do` avec une demande "modèle 3D de …") → poll `/api/ext/3d/status/<id>` (montre `step`+`elapsed_s`) → sur `done` : charge `<base>+glb_url` dans le viewer **et** persiste le `.glb` (Vercel Blob ou commit repo) — §3 + §4.
4. **Conversation** → widget `aurora-embed.js` (mode A) ou `POST /api/ext/chat` / `POST /api/ext/do` direct (mode B). Logge les échanges côté site — §5.
5. **Code / firmware** (Arduino, ESP, scripts…) → `POST /api/ext/do {request:"…", kind:"code"}` → Markdown avec le code + instructions de flash. Compile/flash de ton côté (l'API n'exécute pas le firmware).
6. Gère `401/403/429/502/524` — §6. Le tunnel peut changer — §7.
