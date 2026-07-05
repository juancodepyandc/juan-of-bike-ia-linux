# Pronote / ENT scolaire — Phase 2 spec (cowork-lead)

User direction (cron loop, 2026-05-03) :
> il doit pas juste regarder cahier de textes notes fichier matière mais
> détecter son environnement car des fois entre site ça fonctionne
> différemment il explore et récupère s'il y a des cours en format pour
> les réarranger et comprendre si il y a des feuille exo pour s'en
> inspirer s'il veut retravailler etc et les devoirs pour les évals et
> devoirs pour comprendre où l'élève en ai dans un chapitre ou autre
> pour l'aider et aussi il puisse regarder les notes pour voir le niveau
> a remonter

---

## Scope élargi — exploration adaptative et compréhension scolaire

L'objectif n'est PAS un scrape figé sur Pronote. C'est un agent qui :

1. **Détecte l'ENT** où l'utilisateur est connecté (Pronote, ÉcoleDirecte,
   Skolengo, ENT IDF/HDF/Occitanie, Klassroom, etc.).
2. **Explore adaptativement** la structure du site (chaque ENT a sa propre
   nav, ses propres terms — "cahier de textes" / "agenda" / "travail à
   faire" / "to-do" / "devoirs maison").
3. **Récupère et classifie** :
   - **Cours** (PDF, DOCX, ODT, slides) → reformatte → comprend la structure
     pédagogique (chapitre / sous-chapitre / objectifs).
   - **Feuilles d'exos** → identifie comme exercices d'inspiration → l'élève
     peut demander à Aurora "refais-moi des exos comme ces feuilles".
   - **Devoirs à faire** → contexte (chapitre + matière + date limite +
     modalité éval ou non).
   - **Devoirs faits** → si retournés notés, voit où l'élève s'est trompé
     pour cibler la révision.
   - **Notes** → trend par matière, identifier celles "à remonter"
     (sous la moyenne classe, ou en baisse trimestre vs précédent).
4. **Synthétise un état pédagogique** :
   - Pour chaque matière : niveau actuel + chapitres récents + prochaine éval +
     gaps détectés (exos jamais rendus, chapitre sauté, note basse récente).
5. **Propose des actions** :
   - Notif push (toggleable) X jours avant éval avec rappel chapitre.
   - "Veux-tu un parcours révision ?" → génère cours + flashcards + exos
     calibrés sur le chapitre détecté + le niveau actuel.
   - Pour chaque feuille d'exo trouvée : "Refaire 3 variantes inspirées" /
     "Corriger pas-à-pas".

---

## Contraintes techniques

### Aurora-Connect Chrome extension est obligatoire
Toutes les pages ENT exigent une session auth (cookies). Le bridge Python
en server-side ne peut pas (légalement et techniquement) re-jouer la session
sans que l'user lui donne ses creds. La seule voie propre : Aurora-Connect
qui tourne dans le navigateur de l'user (déjà loggué) et exécute des
queries DOM.

### Étapes d'implémentation (cowork-lead pipeline)

**P2.1 — Site detection** (`coworkConnectors.ts`)
- Adapter dispatcher : si `window.location.hostname` matche
  `*.index-education.com` → connector Pronote, sinon ÉcoleDirecte etc.
- Connector minimal : detect that user is authenticated (présence de
  certains DOM markers) + fournir une `homeMap()` qui retourne les URLs
  des principales sections (cahier de textes, notes, fichiers).

**P2.2 — Document harvest** (`coworkPlanner.ts` + `coworkExecutor.ts`)
- Plan multi-step : open cahier de textes → for each devoir, open detail
  → list pièces jointes → download (extension renvoie blobs au bridge
  via inbound endpoint).
- Bridge stocke les blobs par discipline + date dans `output/pronote/{user}/`.

**P2.3 — Document parsing**
- PDFs via `pdfjs-dist` (déjà bundlé via `pdf-DxKEuLOw.js`) → texte +
  bbox.
- DOCX via `mammoth` (déjà bundlé) → texte structuré.
- LLM pass : qwen3-32b prompt "extrait le chapitre, les sous-points, le
  niveau scolaire" → structured JSON.

**P2.4 — Notes harvest + trend analysis**
- Connector Pronote : open Notes → extract DOM table → JSON
  `{matière, date, note, classe_avg, type}`.
- Trend : last N notes per matière → moving avg → flag matières en baisse.

**P2.5 — Eval detector**
- Cahier de textes → for each devoir, check label ("DM", "DST",
  "interrogation", "éval", "contrôle") → flag.
- Date limite + LLM pass pour décider "c'est éval ou pas".

**P2.6 — Notification scheduler**
- Service worker + `Notification.permission` (déjà câblé v82gj).
- Toggle dans Settings → "Notifs Pronote" + "Préavis : 1j / 3j / 7j".
- À chaque tick (background sync), check les évals à venir, si dans
  préavis et pas notif déjà envoyée → push.

**P2.7 — Parcours révision builder**
- Reuse `learningSessionStore` + `flashcardsStore`.
- Inputs : matière + chapitre + niveau (depuis P2.3) + dernières évals.
- LLM prompt structuré → génère :
  - 3-5 fiches de révision (résumé + définitions clés).
  - 5-10 flashcards avec answer.
  - 3 exos type avec correction étape par étape.
  - Mind-map du chapitre.

**P2.8 — UI** (V1 Academy module)
- Nouvelle section "🏫 Mon ENT" en tête.
- Card par matière avec :
  - Note actuelle / classe avg / trend ▲▼.
  - Prochaine éval (date + chapitre).
  - Bouton "🎯 Préparer cette éval" → lance P2.7.
  - Bouton "📂 Voir les cours" → liste pièces jointes harvest P2.2.

---

## Fichiers à créer / modifier

```
application/src/services/
  ├── pronoteAdapter.ts           NEW — site detection + DOM markers
  ├── ecoleDirecteAdapter.ts      NEW
  ├── skolengoAdapter.ts          NEW
  └── entAdapterRegistry.ts       NEW — dispatcher

application/src/services/
  ├── coworkConnectors.ts         MOD — ajout 3 connecteurs ENT
  └── coworkPlanner.ts            MOD — plan harvest

application/python-services/
  └── ent_harvest.py              NEW — endpoint reception blobs
                                    + parsing PDF/DOCX
                                    + persistance par user

application/bridge_server.py      MOD — routes /api/ent/{harvest,
                                    list-files, eval-list, notes-trend,
                                    revision-parcours}

application/src/stores/
  ├── entSessionStore.ts          NEW — état "logged-in" par ENT,
                                    last-harvest timestamp, files index
  └── entNotificationStore.ts     NEW — schedule + sent log

application/src/views/
  └── AuroraV1AcademyView.tsx     MOD — section "Mon ENT" en tête
```

---

## Estimations

- P2.1 site detection : 1-2 jours.
- P2.2 harvest pipeline : 2-3 jours (Aurora-Connect blob upload + bridge
  persist).
- P2.3 parsing : 1-2 jours (réutilise pdfjs/mammoth + LLM JSON).
- P2.4 notes trend : 1 jour.
- P2.5 eval detect + LLM classifier : 1 jour.
- P2.6 notif scheduler : 1 jour (déjà 80% câblé via PWA push).
- P2.7 parcours builder : 2 jours (réutilise les stores existants).
- P2.8 UI Academy section : 1-2 jours.

**Total estimé : 10-14 jours** de dev focused. Pas faisable en une iter
de 5 min de cron — à découper en passes successives.

---

## Phase 1 livrée (v82jc) qui fait quoi maintenant

- ✅ Bridge proxy ICS → bypass CORS sur les flux .ics publics.
- ✅ 5 portails école avec icons + finder.
- ✅ Détection extension Aurora-Connect (warning si absent).

C'est la fondation. Phase 2 builds dessus.
