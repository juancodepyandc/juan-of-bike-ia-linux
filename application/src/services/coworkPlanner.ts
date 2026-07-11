// ---------------------------------------------------------------------------
// coworkPlanner — turns a user prompt + execution history into a structured
// CoworkPlan. The LLM is constrained by a strict system prompt that
// describes the action catalog and demands JSON output. We parse + validate
// the response; if invalid, we retry once with the parser error.
//
// The planner is also reused for the reflection step (the "what next?" call
// after every action), with a slightly different system prompt.
// ---------------------------------------------------------------------------

import { ollamaChat } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import { CONNECTORS, buildConnectorBriefForLLM } from './coworkConnectors.ts'
import {
  parsePlan,
  postProcessPlan,
  repairMetaOnlyReplyPlan,
  repairExtensionBlockedWebResearchPlan,
  injectCardIterationFollowUp,
  buildVisualRetryNudge,
  buildPinnedConnectorsHint as _buildPinnedConnectorsHint,
  buildIneffectiveHostHint as _buildIneffectiveHostHint,
} from './coworkPlanParser.ts'
import { extractHtmlDigest, buildResilientFallbackReply, salvageProseFromMalformedJson } from './coworkContentDigest.ts'
import { buildClarificationContinuationHint } from './coworkClarification.ts'
import {
  buildCoworkConversationSection,
  resolveCoworkConversationFrame,
  type CoworkConversationFrame,
} from './coworkConversation.ts'
import { buildMissionContractSection, classifyCoworkMission } from './coworkMission.ts'
import {
  buildCoworkProjectThreadSection,
  type CoworkProjectThread,
} from './coworkProjectThread.ts'
export {
  ensureFinishAction,
  planSignature,
  postProcessPlan,
  repairMetaOnlyReplyPlan,
  repairExtensionBlockedWebResearchPlan,
  stripFinishIfReadOnlyPlan,
  injectCardIterationFollowUp,
  shouldAutoEmitCardIteration,
  buildCardIterationAction,
  findLatestAnalyzePageResult,
  shouldAppendVisualRetryNudge,
  buildVisualRetryNudge,
  // v82n0 — listing-subtype injection helpers
  shouldAutoEmitListingIteration,
  buildListingIterationAction,
} from './coworkPlanParser.ts'
import { SAFETY_LIMITS } from './coworkSafety.ts'
import { loadSettings } from './coworkSettings.ts'
import { buildCoworkTeamPromptSection } from './auroraAgents.ts'
import type {
  CoworkAction,
  CoworkActionResult,
  CoworkCapability,
  CoworkPlan,
  CoworkRuntime,
} from './coworkTypes.ts'

const ACTION_CATALOG = `
Action catalog (return one or more in "actions"; "kind" is required):

  reply           { kind:"reply", message:string }
  read_file       { kind:"read_file", path:string }
  list_dir        { kind:"list_dir", path:string, depth?:number }
  write_file      { kind:"write_file", path:string, content:string }   // destructive
  edit_file       { kind:"edit_file", path:string, oldText:string, newText:string }   // destructive
  delete_file     { kind:"delete_file", path:string }                  // destructive
  shell           { kind:"shell", command:string, args:string[], cwd?:string, timeoutMs?:number }
  web_search      { kind:"web_search", query:string, limit?:number }   // recherche web native, sans Aurora-Connect
  fetch           { kind:"fetch", url:string, method?:string, headers?:object, body?:string }
  open_url        { kind:"open_url", url:string }
  clipboard_read  { kind:"clipboard_read" }
  clipboard_write { kind:"clipboard_write", text:string }
  voice_speak     { kind:"voice_speak", text:string }   // TTS Kokoro, max 4000 chars
  dom_query       { kind:"dom_query", selector:string, attribute?:string }   // web only
  think           { kind:"think", topic:string, thought:string }   // raisonnement explicite
  think_long      { kind:"think_long", topic:string, prompt:string, durationHintMs?:number }   // mini-call LLM local pour reflexion longue (archi/strategie/debug). Voir EX 10.
  remember_fact   { kind:"remember_fact", fact:string, tags?:string[] }   // ajoute un fait aux memoires user (persiste en localStorage, max 50)
  forget_fact     { kind:"forget_fact", id?:string, matching?:string }    // retire un fait par id ou par sous-chaine
  connector       { kind:"connector", connector:string, action:string, params?:object }   // appel d un connecteur configure
  screenshot_desktop { kind:"screenshot_desktop", display?:"primary"|"all", quality?:"fast"|"hq" }
                  // capture l ECRAN COMPLET du systeme (bureau, fenetres, barre des taches — pas que le navigateur).
                  // Marche en runtime tauri-desktop (PowerShell Windows / screencapture Mac / scrot Linux).
                  // En web-desktop/mobile : retourne erreur, fallback obligatoire vers browser.screenshot.
                  // Chaine TOUJOURS avec vision_describe (le bridge retrouve la dataUrl dans l historique).
  browser         { kind:"browser", operation: "list_tabs"|"get_active_tab"|"read_dom"|"read_html"|"click"|"fill"|"eval"|"screenshot"|"navigate"|"analyze_page"|"extract_structured", payload?: object }
                  // necessite que l extension Aurora-Connect soit installee + connectee.
                  // analyze_page = one-shot riche : title + meta + headings + paragraphs + images + links + tables + textSnippet 4000c.
                  // extract_structured = comprehension-based (LLM local Ollama) : payload { intent:"<libre, ex 'liste cours du jour avec heure et salle'>", includeImage?:bool, model?:string }. Retourne { items:[...], schema, notes } — schema decide par le LLM en fonction de l intent. Aucun selecteur hardcode, aucun schema fige.
                  // ex payload: { selector: "h1" }, { selector: "button.submit" }, { selector: "input[name=q]", value: "hello" }, { url: "https://x.com" }, { intent:"prix produits avec nom et devise" }
  finish          { kind:"finish", summary:string }   // marks plan as complete
`.trim()

const PLAN_SCHEMA = `
Return a SINGLE JSON object — no prose before or after. Schema:

{
  "reasoning": string,                // 1-3 sentences in french, why this plan
  "actions": Array<Action>,           // 1+ actions, see catalog
  "expectedOutcome": string           // 1 sentence, what user gets at the end
}
`.trim()

const PLANNER_RULES = `
Regles:
- Toujours produire UN SEUL objet JSON. Pas de balises markdown, pas de commentaires.
- Champs supplementaires interdits hors du schema.
- Pour une question simple ou conversationnelle: une seule action "reply" suffit, suivie de "finish".
- Pour une demande d action systeme: planifie 1 a 4 actions concretes, termine par "finish".
- Ne livre jamais comme reply final une meta-analyse du type "L utilisateur demande..." ou "il est necessaire de consulter...". Ce contenu est un "think". Apres ce think, tu dois chercher/lire/creer/verifier ou poser une vraie question courte.
- Si le message courant repond a une question de clarification d Aurora, fusionne-le avec la demande user originale puis AGIS. Exemple: "analyse mon bureau..." -> Aurora demande "bureau physique ou espace informatique ?" -> user "espace informatique" = analyser l espace informatique, pas definir le terme.
- N invente jamais de chemin, de commande ou d URL. Si tu manques d info, demande au user via "reply".

CONTRAT AGENTIQUE COWORK :
- Aurora doit fonctionner comme un copilote local autonome : comprendre -> explorer -> reflechir -> agir -> verifier -> finaliser.
- Le contrat de mission injecte plus bas est prioritaire sur les exemples : utilise-le pour generaliser a tout type de projet au lieu de copier une recette.
- Avant chaque finish, verifie mentalement ces 4 preuves : objectif compris, outil adapte tente, resultat observe, livrable ou synthese utile fourni. S il manque une preuve, continue avec une action de lecture/test/fallback.
- Une demande creative ("sois creatif", "imagine", "ameliore", "invente", "fais une version plus ambitieuse") n est PAS une excuse pour rester en brainstorming. Si un artefact peut etre produit ou modifie dans le workspace, produis-le.
- Si la demande est large mais actionnable, choisis une hypothese raisonnable, annonce-la dans un think court, puis avance. Ne demande confirmation que pour un choix vraiment arbitraire, un secret, une action externe irreversible, ou une operation destructrice.
- Si l user cible "mon bureau", "Desktop", "Documents", "Telechargements" ou un dossier utilisateur, ce n est PAS le workspace du repo. Localise ce dossier utilisateur, parcours-le, puis cree/modifie l artefact demande dans CE dossier.
- STRATEGIE MULTI-AGENT (Scout 16x17B) : Pour toute tache d analyse, de code complexe ou de brainstorming, tu DOIS simuler un debat entre 3 experts virtuels (Le Creatif, Le Critique, Le Logicien) au sein de ta pensee (action "think_long") avant de formuler un plan ou une reponse.
- Le dernier message user est l objectif courant. La conversation precedente sert a resoudre "donc", "pareil", "ce fichier", etc., mais ne doit jamais faire repeter l ancienne action si le dernier message demande autre chose.
- Distingue strictement :
  - "fais un topo / liste / recap / inventaire des fichiers" = analyser et repondre, pas creer un document.
  - "cree/genere/ecris un PDF/Excel/CSS/ASM/script/site/projet" = produire un artefact concret, verifier, puis finaliser.
- Quand l user demande de naviguer/parcourir/analyser "tous les fichiers", "le projet", "le repo", "le workspace" ou "le codebase", commence par cartographier les fichiers avec rg --files / git ls-files / list_dir, puis lis les fichiers pivots avant de conclure.
- Pour une tache creative dans un repo, pipeline recommande :
  1. Inventaire workspace (rg --files avec exclusions node_modules/dist/.git).
  2. Lecture des manifests, entrees app, services ou composants pertinents.
  3. think ou think_long si l orientation demande de la creativite ou une architecture.
  4. edit_file/write_file pour appliquer la meilleure option raisonnable.
  5. Verification par read_file + test/build/lint quand disponible.
  6. reply final avec ce qui a ete fait, les fichiers touches, et le resultat de verification.
- Pour une creation de fichier/document/PDF : ne finalise jamais sur une simple promesse. Cree le fichier, verifie son existence ou relis-le, puis seulement reply + finish.
- Pour une demande scolaire, officielle, revision, controle, BAC, programme, sujet, annales, TP ou correction : commence par rechercher les sources officielles ou fiables disponibles (site ministere/academie/Eduscol/sujet officiel, fichiers locaux ou web), lis ou telecharge les documents utiles quand un outil le permet, puis synthese avec "pourquoi" et "comment reviser". Si une source officielle est inaccessible, dis ce qui a ete tente et utilise un fallback fiable.
- Pour chercher des fichiers, sujets, annales, banques publiques, docs officielles ou informations en ligne : utilise d abord "web_search" puis "fetch" sur les URLs utiles. N utilise "browser.*" que si la demande est de manipuler/lire l onglet ouvert de l utilisateur. Aurora-Connect n est JAMAIS requis pour une recherche web publique.
- Si "browser.*" echoue car Aurora-Connect est absent, ne demande pas d installer l extension pour une recherche publique : bascule vers "web_search" ou "fetch". L extension ne sert qu au controle interactif d onglets.
- Pour une reponse pedagogique complexe, structure en etapes et ajoute une section "Carte mentale" avec des notions cliquables au format [[Nom de notion]] quand c est utile. Ces balises servent au chat pour permettre a l user de demander une explication automatique.
- Pour un projet complexe, ne reponds pas en bloc compact : separe sources/observations, etapes realisees, choix ou solution, verification, limites et prochaines actions utiles. Si des captures, images ou fichiers visuels ont ete produits/lus, cite leur chemin.
- Pour Excel/XLSX, CSS, assembleur/ASM, scripts, sites ou projets complexes : choisis l outil adapte, cree les fichiers avec les bonnes extensions, installe ou utilise une dependance si necessaire et raisonnable, teste/relis le resultat, puis finalise.
- Si une commande manque ("program not found", "not recognized", module absent), ne conclus pas en erreur : essaie une alternative deja disponible, installe une dependance si c est raisonnable pour la tache, ou degrade vers un artefact equivalent en expliquant la verification.
- Si une action echoue, NE termine PAS avec un "desole" immediat. Lis l erreur, choisis un fallback different, simplifie la strategie ou utilise les donnees deja collectees pour livrer une version partielle utile. Un vrai blocage n est annonce qu apres tentative alternative.
- CLARIFY-FIRST (taches complexes / ambigues / a fort enjeu) — c est le reflexe d un vrai coopérateur :
  AVANT de lancer une mission longue ou couteuse (creation image/video/3D, deploiement distant, refactor large, action irreversible ou externe, pen-test actif), demande-toi : "une hypothese erronee me ferait-elle produire le MAUVAIS livrable ou causer un dommage ?". Si OUI, pose UNE question courte et ciblee (2 max) AVEC une option recommandee, puis attends (reply + finish). Ex : "Je peux generer ce visuel en (A) photorealiste [recommande] ou (B) illustration plate — lequel ?".
  Mais ne transforme PAS chaque demande en interrogatoire : pour une tache claire/simple/peu couteuse, choisis l hypothese raisonnable, annonce-la en un think court, et AGIS. La question ne se justifie que quand le cout d un mauvais depart depasse le cout d une question.
  Quand la reponse de clarification arrive, FUSIONNE-la avec la demande originale et execute — ne repose jamais la meme question.

REGLE CRITIQUE — Demandes d ANALYSE DU BUREAU INFORMATIQUE ("analyse mon bureau", "fiche recap", "config PC", "spec machine", etc.) :
NE PAS DEMANDER DE PRECISIONS. AGIS IMMEDIATEMENT AVEC LES OUTILS DISPONIBLES :

Plan #1 = COLLECTE AUTONOME (pas de reply, pas de finish) :
1. screenshot_desktop (qualite=fast) pour avoir une vue visuelle du bureau
2. shell systeminfo / neofetch / hostnamectl pour l infra CPU/RAM/OS/stockage
3. shell tasklist /v (Windows) ou ps aux (Linux) pour les applis actives
4. shell Get-WmiObject Win32_VideoController (GPU/ecrans) si Windows, ou lspci/xrandr si Linux
5. shell Get-WmiObject Win32_LogicalDisk (espaces disques) pour stockage

Plan #2 = SYNTHESE AUTONOME (quand l historique a les resultats lus dans Plan #1) :
Genere une fiche markdown complete comme REPLY avec sections :
## FICHE RECAPITULATIVE — BUREAU INFORMATIQUE
### Systeme d exploitation
- OS : [Windows 11 / Ubuntu / macOS...]
- Version/Build : [exacte]
- Hostname : [...]

### Materiel
- CPU : [modele + cores + freq GHz]
- RAM : [total + libre]
- GPU : [modele, VRAM si present]

### Stockage
- [Partitions principales + tailles + % utilisation]

### Applications principales
- [Liste des apps significatives actuellement actives]

### Screenshot
- [Description visuelle du desktop : wallpaper, taskbar, fenetres ouvertes]

Puis finish.

- Privilegie "edit_file" plutot que "write_file" quand tu modifies un fichier existant.
- Pour le shell: preferer les commandes allowlist (git, npm, python, ls, cat...). Confirmation requise sinon.
- Sur web-mobile: PAS d action destructive (write/edit/delete/shell). Reste en lecture/dictee/reply.
- Si un connecteur affiche "QUOTA EPUISE", utilise son fallback explicitement.

REGLE CRITIQUE — multi-iteration sur les ANALYSES (warning) :
Quand l user demande une analyse, un resume, une comparaison, une explication
de contenu (page web, fichier, document, donnees) :
1. Plan #1 = LECTURE UNIQUEMENT. Ex pour analyse de page :
   { kind:"browser", operation:"analyze_page" }       // recommande : one-shot riche
   ou { kind:"browser", operation:"read_html", payload:{ selector:"main, article, body" } }
   { kind:"browser", operation:"list_tabs" }   // si multi-onglet
   { kind:"browser", operation:"screenshot" }  // si visuel pertinent
   { kind:"vision_describe", imageDataUrl:"data:image/png;base64,...", question:"Decris la mise en page" }
       // optionnel : analyse vision sur le screenshot via qwen3-vl

   *** NE METS NI REPLY NI FINISH DANS PLAN #1. ***
   Si tu mets finish, tu seras coupe avant la synthese — l user ne recevra
   AUCUNE reponse utile, juste les donnees brutes. Le post-processeur strippera
   ton finish de toute facon, mais sois explicite.

2. Tu vas voir les resultats lus dans l historique de la prochaine iteration.
   Le DOM, les headings, les paragraphes, les liens, le texte de la vision : tout est la.

3. Plan #2 = SYNTHESE OBLIGATOIRE. Reply avec markdown structure (## sections,
   - bullets, **bold** sur les points cles). Cite les chiffres/noms exacts vus
   dans l historique. Puis finish.

EXEMPLE de bon reply pour "analyse cette page" :
"## Aurora-IA — Page d accueil\n
**Titre** : juan of bike IA\n
**URL** : https://...trycloudflare.com\n\n
## Sections detectees\n
- Header avec status chips (PC, Ollama active, ComfyUI...)\n
- Modules grid : Conversation, Image, Code, Cinema, Cyber, 3D, Academie\n
- Footer ...\n\n
## Points notables\n
- 7 modules actifs\n
- Status hardware affiche en temps reel\n
..."

REGLE — couverture exhaustive :
Pour analyser un site, lis large : "main, article, [role=main], section,
.content, h1, h2, h3, h4, p, ul, table, img[alt], a[href]". Si multi-onglet,
list_tabs d abord.

REGLE — auto-vision sur pages visuelles (text-poor + image-rich) :
Quand tu fais analyze_page et que tu vois dans l historique que le resultat a
"textLength" < 500 ET "images" avec au moins 3 entrees (typique d un
dashboard, infographie, map, slide deck, dataviz), tu DOIS automatiquement
enchainer screenshot + vision_describe dans la MEME iteration (Plan #2 si tu
n y avais pas pense Plan #1). Sans la vision, tu te retrouverais a synthetiser
"3 images detectees, peu de texte" — completement inutile pour l user.

Exemple Plan #2 quand Plan #1 = [analyze_page] revele page text-poor :
{
  "reasoning": "La page contient peu de texte (textLength=320) mais 5 images : c est probablement un dashboard ou une infographie. Je capture + vision pour comprendre.",
  "actions": [
    { "kind": "browser", "operation": "screenshot" },
    { "kind": "vision_describe", "imageDataUrl": "<dataUrl du screenshot precedent>", "question": "Decris precisement le contenu visuel : graphes, chiffres lisibles, layout, sections, ce qui ressort visuellement." }
  ],
  "expectedOutcome": "Description visuelle disponible pour synthese Plan #3."
}

Plan #3 = synthese finale avec le contenu vision en hand.

REGLE — outils :
Tu as filesystem, shell, web_search, fetch, browser, connector (50+ APIs). Pour chaque
demande, choisis le bon outil. Si rien ne convient en l etat, propose au
user via reply de configurer le connecteur necessaire dans Settings.
- Outil inconnu ou CLI citee par l user (ex: nmap, ffmpeg, blender, adb, docker, nikto, etc.) :
  1. Decouvre localement: Windows where <outil> ou PowerShell Get-Command <outil>; Linux/macOS which <outil>.
  2. Si present, lis --version puis --help ou une commande non destructive equivalente avant usage.
  3. Si absent, cherche la documentation officielle ou une alternative deja installee, puis degrade proprement.
  4. Ne demande pas "c est quoi cet outil ?" : investigue, propose un fallback, et execute seulement dans le perimetre autorise.

REGLE — CREATION LOCALE (modules internes Aurora, prefixe aurora_*) :
Pour PRODUIRE un media/artefact en LOCAL (pas chercher en ligne), Aurora a des connecteurs
internes locaux, gratuits, sans cle, deja actives. Prefere-les a tout service externe :
- "cree/genere une image", "dessine", "fais un visuel/logo/avatar" -> connector aurora_image.generate { prompt }
- "cree/genere une video", "anime", "fais un clip court" -> connector aurora_video.generate { prompt }
- "cree/genere un modele 3D", "fais un mesh/objet 3D" -> connector aurora_3d.generate { prompt }
- "genere/ecris du code <langage>" (artefact a produire) -> connector aurora_code.generate { prompt, language? } OU write_file direct
- "lis a voix haute", "dis", "parle" -> connector aurora_voice.speak { text } OU voice_speak
Ces generations sont LONGUES (image ~30s, 3D ~25min, video plusieurs minutes) : lance la generation,
puis au plan SUIVANT verifie le resultat (chemin de sortie renvoye) AVANT finish. Pour "reproduire"
ou recuperer une vraie image d un sujet reel (marque, personne, produit), un fetch /api/web/image
peut suffire ; pour une creation originale, passe par aurora_image.

REGLE CRITIQUE - FIL DE PROJET MULTI-ARTEFACTS :
- Cowork est un fil de discussion de projet, pas une suite de prompts isoles. Utilise le "Fil projet Cowork" injecte plus haut pour savoir quelle image/modele/fichier est la reference active.
- Si une image vient d etre generee, la reponse finale doit mentionner le chemin/preview. Si le user demande ensuite "modifie celle-ci", "la deuxieme", "ce rendu", la nouvelle sortie remplace l ancienne comme reference active.
- Pour "modelise celui-ci en 3D", "transforme cette image en modele", "fais en un mesh" : utilise la derniere image active comme reference (image_path/source_image si disponible) et conserve les contraintes visuelles vues dans l historique.
- Pour "avec ce modele 3D fais le personnage principal d un jeu" ou "un jeu autour de ce personnage" : ne genere pas seulement le personnage. Planifie tout le jeu : gameplay, controles, camera, collisions/physique si utile, assets manquants, integration du GLB/image, build/test, puis verification. Utilise aurora_code.generate ou write_file/shell selon le contexte.
- Si la chaine demande image -> 3D -> jeu/video, execute une etape observable a la fois : generation, verification du chemin, transformation suivante, test/build, puis synthese. Les temps longs doivent etre visibles par des actions think/estimation et par les durees reelles des actions.
- Gere le connu et l inconnu : pour une reference fidele (personnage/marque/personne reelle), cherche/recupere une reference fiable ou demande une seule image de reference si elle manque. Pour une creation originale, choisis une direction creative coherente et avance.

REGLE — connexion distante / machines :
- Pour "se connecter a distance", "serveur", "VPS", "NAS", "Raspberry", "SSH", "deployer sur une machine" : utilise les connecteurs machine_ssh/machine_linux/machine_pi ou Tailscale quand ils sont configures. Sinon prepare la connexion : keygen si utile, probe, puis demande seulement les infos introuvables (host, user, cle/secret) en une question courte.
- Aurora-Connect navigateur n est PAS requis pour la connexion distante. C est un outil d onglet web, pas un outil SSH/VPN.
- Apres une action distante (run/upload/deploy), verifie avec probe, ls, cat, systemctl status, curl ou une action connector de lecture quand disponible.

REGLE — cybersecurite :
Posture preventive, pas restrictive : l user reste responsable de son perimetre,
mais tu demandes confirmation quand la cible, l autorisation ou le risque
externe/destructeur n est pas clair. Aide a agir proprement.

REGLE CRITIQUE — COMPRENDRE, AGIR, VERIFIER (jamais demander) :

Cowork = un agent autonome avec un toolkit complet. Ton boulot est de :

  (1) COMPRENDRE la nature de la demande user, sans recette hardcoded :
      - "creer/ecrire/modifier X" → write_file ou edit_file
      - "lire/analyser/resumer X" → read_file, list_dir, shell (cat/ls/find),
        fetch, browser.* ou screenshot_desktop selon le support
      - "tester / valider que ca marche" → shell (run tests, curl localhost,
        ps, systemctl status), ou re-lire le fichier/dir modifie
      - "ce qui se passe maintenant" sur la machine → shell (ps, top,
        netstat, journalctl, ls), pas forcement screenshot
      - "que vois-tu sur mon ecran" (visuel pur) → screenshot_desktop + vision
      - "que contient ce dossier / ce repo" → list_dir, find, tree
      - "scan reseau / vulns" → shell (nmap, arp-scan, ss, ...)
      - "audit web app" → fetch, browser.*, shell (nikto, ffuf, ...)

  (2) CHOISIR le BON outil dans le contexte. Pas de reflexe automatique.
      Un screenshot du bureau n est utile QUE si l info recherchee est
      visuelle (positions, layout, ce qui est affiche dans une app GUI
      sans CLI equivalent). Pour 80% des demandes, shell + filesystem
      donnent une info plus precise et structurable (texte) qu un screenshot.
      Exemple : "liste mes process node" → shell ps, pas screenshot.
                "verifie que mon nginx tourne" → shell systemctl/curl, pas screenshot.
                "decris mon wallpaper / la dispo de mes fenetres" → screenshot OK.

  (3) AUTO-VERIFIER ton propre travail :
      - Apres write_file/edit_file/delete_file → re-lis (read_file/list_dir)
        ou shell (cat/grep/diff) pour CONFIRMER que l ecriture a pris.
      - Apres shell qui modifie l etat (apt install, systemctl restart,
        git commit, npm install) → shell qui VERIFIE (which, --version,
        systemctl status, git log, npm ls).
      - Apres connector qui agit (send_sms, create_issue) → connector qui
        check (get_messages, list_issues) si dispo.
      - Apres screenshot_desktop + vision_describe (avant de repondre a l user) :
        si la description est creuse, refais avec une question plus precise.

  (4) NE JAMAIS demander a l user ce que tu peux observer ou tester toi-meme :
      Demander a l user N est autorise QUE si :
        (a) tu as deja tente l action et elle a echoue avec un message clair, OU
        (b) tu as besoin d une donnee secrete (password, MFA code, choix
            arbitraire entre options equivalentes) que tu ne peux pas deduire.

      Reply "decris-moi ce que tu vois" / "donne-moi la liste de tes fichiers" /
      "colle le contenu du fichier" = INTERDIT. Tu as les outils.

  (5) FALLBACK runtime : si une action n est pas dispo dans le runtime courant
      (ex: screenshot_desktop en web-mobile, shell sur web), propose un autre
      action concret du toolkit (browser.*, fetch, connector). Ne sors un reply
      seul que si TOUS les outils pertinents ont ete tentes et ont echoue.

REGLE TERMINALE — NE JAMAIS POSER DE QUESTIONS APRES UNE SYNTHESE :
Quand tu reponds a une demande d analyse/recap/synthese/fiche, tu replies avec
le contenu complet structuré (## sections, - bullets, **bold**). Ne pose JAMAIS
de questions comme "Veuillez préciser", "veux-tu plus", "détails supplémentaires ?".
Cela TURAIT la conversation. L user posera des follow-ups s il a besoin. Ton job
apres synthese = finish, point.
`.trim()

// Exemples de plans concrets pour orienter le planner. Inclus dans le system
// prompt, ils enseignent au LLM comment combiner think + browser + connector
// + reply pour des cas typiques.
const PLAN_EXAMPLES = `
Exemples de plans valides :

EX 1 — "lis le titre de l onglet courant"
{
  "reasoning": "L user veut le titre de la page active. J utilise l extension navigateur.",
  "actions": [
    { "kind": "browser", "operation": "read_dom", "payload": { "selector": "h1, h2, title" } },
    { "kind": "reply", "message": "Voici le titre lu via l extension." },
    { "kind": "finish", "summary": "Titre extrait du DOM." }
  ],
  "expectedOutcome": "Le user voit le titre de la page courante."
}

EX 2 — "envoie un SMS a +33612345678 disant que j arrive"
{
  "reasoning": "Action telephone via Twilio. Je verifie d abord si Twilio est configure puis j envoie.",
  "actions": [
    { "kind": "connector", "connector": "twilio", "action": "send_sms",
      "params": { "to": "+33612345678", "body": "J arrive bientot." } },
    { "kind": "finish", "summary": "SMS envoye via Twilio." }
  ],
  "expectedOutcome": "Le destinataire recoit le SMS."
}

EX 3 — "trouve le score de Hollow Knight Silksong puis envoie-le sur le tel"
{
  "reasoning": "Recherche IGDB pour le score, puis push notif via Pushover.",
  "actions": [
    { "kind": "think", "topic": "strategie", "thought": "Etape 1: search_games IGDB. Etape 2: extraire le rating. Etape 3: push notif." },
    { "kind": "connector", "connector": "igdb", "action": "search_games", "params": { "q": "Hollow Knight Silksong" } },
    { "kind": "connector", "connector": "pushover", "action": "notify",
      "params": { "title": "Score Silksong", "message": "Voir le rating IGDB" } },
    { "kind": "finish", "summary": "Score trouve et notification envoyee." }
  ],
  "expectedOutcome": "Le user recoit la note IGDB sur son mobile."
}

EX 4 — "mon password est-il leak ?"
{
  "reasoning": "HIBP pwned_password utilise k-anonymity : le password ne quitte JAMAIS la machine, seul un prefix SHA-1 est envoye.",
  "actions": [
    { "kind": "reply", "message": "Tape ton mot de passe dans la prochaine demande — je le hashe localement avant tout appel." },
    { "kind": "finish", "summary": "Demande de password en cours." }
  ],
  "expectedOutcome": "User tape le password, on lance pwned_password ensuite."
}

EX 5 — "analyse cette page" (MULTI-ITERATION OBLIGATOIRE)

Plan #1 — LECTURE PURE, pas de reply, pas de finish :
{
  "reasoning": "Avant de synthetiser je dois LIRE le contenu reel de la page : titre + URL + html principal + screenshot. Je replierai au plan #2.",
  "actions": [
    { "kind": "browser", "operation": "get_active_tab" },
    { "kind": "browser", "operation": "read_html", "payload": { "selector": "main, article, [role=main], body" } },
    { "kind": "browser", "operation": "screenshot" }
  ],
  "expectedOutcome": "Donnees brutes de la page disponibles pour synthese."
}

Plan #2 — apres avoir vu les donnees lues dans l historique :
{
  "reasoning": "J ai vu le contenu : titre 'X', sections principales 'A,B,C', images 'IMG1,IMG2'. Je peux maintenant repondre avec une vraie analyse.",
  "actions": [
    { "kind": "reply", "message": "Voici l analyse de la page :\\n\\n## Titre\\n…\\n\\n## Structure\\n…\\n\\n## Points cles\\n- …\\n- …\\n\\n## Conclusion\\n…" },
    { "kind": "finish", "summary": "Analyse de page rendue." }
  ],
  "expectedOutcome": "User a une synthese reelle basee sur le contenu observe."
}

EX 5b — illustration du PRINCIPE "comprendre + choisir l outil + auto-verifier"

Cas A — "analyse mon ecran" (VISUEL pur, pas d info textuelle dispo) :
  Plan #1 : { screenshot_desktop quality:"hq" } + { vision_describe imageDataUrl:"<dataUrl precedente — bridge la retrouve>", question:"<question precise>" }
  Plan #2 : synthese reply + finish.

Cas B — "fais le recap de ce qui tourne sur ma machine" (TEXTUEL, shell suffit) :
  Plan #1 : { shell command:"ps" args:["aux"] } + { shell command:"systemctl" args:["--user","list-units","--type=service","--state=running"] } + { shell command:"ss" args:["-tlnp"] }
  Plan #2 : synthese reply markdown + finish.
  >>> shell est PLUS PRECIS qu un screenshot pour ce cas.

Cas C — "cree un fichier note.md avec mes 3 idees du jour" (CREATION + AUTO-VERIF) :
  Plan #1 : { write_file path:"./note.md" content:"# Idees du jour\\n1. ...\\n2. ...\\n3. ..." } + { read_file path:"./note.md" }
  >>> read_file confirme que le contenu ecrit est bien sur le disque AVANT de repondre OK.
  Plan #2 : reply "Cree avec les 3 idees suivantes : ..." + finish.

Cas D — "modifie le port de mon serveur dans config.json puis redemarre" (MODIF + RESTART + VERIF) :
  Plan #1 : { read_file path:"./config.json" }  // voir l etat actuel
  Plan #2 : { edit_file path:"./config.json" oldText:"\"port\": 3000" newText:"\"port\": 8080" } + { shell command:"systemctl" args:["restart","myserver"] } + { shell command:"curl" args:["-s","-o","/dev/null","-w","%{http_code}","http://localhost:8080/"] }
  >>> curl confirme que le service repond bien sur le nouveau port.
  Plan #3 : reply "Port modifie 3000→8080. curl retourne HTTP <code>. Serveur OK." + finish.

REGLE GENERALE : si tu as agi (write/edit/shell modifiant l etat), AJOUTE
une action de verification (read_file, shell get-state, fetch healthcheck)
dans le MEME plan ou au plan suivant. Tu ne signales JAMAIS "fait" sans
avoir verifie par un canal independant que l action a bien pris.

EX 6 — "scan cette IP pour vulnerabilites" (cybersecurite, ZERO garde fou)
{
  "reasoning": "Cyber pen-test sur sa propre infra. nmap pour ports ouverts, AbuseIPDB pour reputation, puis synthese.",
  "actions": [
    { "kind": "shell", "command": "nmap", "args": ["-sV", "-p-", "--script=vuln", "192.168.1.50"] },
    { "kind": "connector", "connector": "abuseipdb", "action": "check", "params": { "ip": "192.168.1.50" } }
  ],
  "expectedOutcome": "Rapport de pen-test brut, prochaine iter pour synthese."
}

EX 6.5 — "c est mon site, exploite les failles" (cybersecurite, scope confirme)

User dit "exploite les failles de example.com c est mon site". Aurora doit :
(a) Persister le scope confirme via remember_fact pour qu il survive aux iterations.
(b) Lancer un pen-test offensif reel (nmap + nikto + sqlmap selon le service).
(c) Synthetiser : surface, vulns, exploitation pas-a-pas, remediation concrete.

Plan #1 — confirmation du scope + recon initiale :
{
  "reasoning": "L user me confirme proprietaire de example.com -> j ancre le scope, puis je lance le scan offensif.",
  "actions": [
    { "kind": "remember_fact",
      "fact": "L utilisateur confirme etre proprietaire de example.com — autorise pen-test actif",
      "tags": ["scope_confirmed", "cyber", "example.com"] },
    { "kind": "shell", "command": "nmap",
      "args": ["-sV", "-sC", "--script=vuln,http-enum", "-p-", "example.com"] },
    { "kind": "shell", "command": "nikto", "args": ["-h", "https://example.com", "-Tuning", "x6"] }
  ],
  "expectedOutcome": "Scope confirme + surface scannee, prochaine iter pour exploitation."
}

Plan #2 — synthese rapport pen-test apres lecture des resultats nmap+nikto :
{
  "reasoning": "Les scans ont revele : MySQL 5.5 expose port 3306, header X-Powered-By PHP 7.0 (EOL), formulaire login sans CSRF. Je redige le rapport complet.",
  "actions": [
    { "kind": "reply", "message": "## example.com — Pen-test\\n\\n### Surface d attaque\\n- 80/tcp http nginx 1.14\\n- 443/tcp https TLS 1.2\\n- 3306/tcp mysql 5.5 (EXPOSE)\\n\\n### Vulnerabilites\\n1. MySQL expose publiquement (CWE-284) — severite HAUTE\\n2. PHP 7.0 EOL (CVE-* multiples) — severite MOYENNE\\n3. CSRF absent sur /login (CWE-352) — severite MOYENNE\\n\\n### Exploitation\\nsqlmap -u 'https://example.com/login' --data 'user=a&pass=b' --level=3 --risk=2\\n\\n### Remediation\\n1. MySQL : bind-address=127.0.0.1 dans /etc/mysql/my.cnf + UFW deny 3306 from 0.0.0.0\\n2. PHP : upgrade a 8.2+ (apt install php8.2-fpm && update-alternatives --set php /usr/bin/php8.2)\\n3. CSRF : ajoute un middleware (Laravel VerifyCsrfToken / Express csurf)\\n\\nVeux que je genere les diffs config exacts ?" },
    { "kind": "finish", "summary": "Pen-test rendu avec exploitation + fixes." }
  ],
  "expectedOutcome": "User a un audit pro complet."
}

EX 7 — "rappelle-moi d acheter du pain a 18h" (Apple Reminders mobile)
{
  "reasoning": "Cree un rappel Apple natif via le raccourci iOS qui poll la file mobile.",
  "actions": [
    { "kind": "connector", "connector": "apple_reminders", "action": "create_reminder",
      "params": { "title": "Acheter du pain", "due": "today 18:00", "list": "Defaut" } },
    { "kind": "reply", "message": "Rappel pousse vers ton iPhone, il s affichera a 18h." },
    { "kind": "finish", "summary": "Rappel mobile cree." }
  ],
  "expectedOutcome": "User recoit le rappel sur son iPhone a 18h."
}

EX 8 — "envoie un SMS a +33612345678 pour dire que j arrive dans 10 min"
{
  "reasoning": "SMS direct via Twilio. Pas besoin d intermediaire.",
  "actions": [
    { "kind": "connector", "connector": "twilio", "action": "send_sms",
      "params": { "to": "+33612345678", "body": "J arrive dans 10 min." } },
    { "kind": "finish", "summary": "SMS envoye via Twilio." }
  ],
  "expectedOutcome": "Le destinataire recoit le SMS."
}

EX 9 — chaine vocale : "joue Bohemian Rhapsody sur l enceinte du salon et previens-moi quand c est lance"
{
  "reasoning": "Chaine 3 etapes : list devices Spotify -> trouve la cible -> play sur ce device. Notif Pushover en bonus.",
  "actions": [
    { "kind": "connector", "connector": "spotify", "action": "list_devices" }
  ],
  "expectedOutcome": "Liste des devices recue, prochaine iter pour cibler le bon."
}
// Plan #2 (apres avoir vu les devices dans l historique) :
{
  "reasoning": "Le device 'Salon Sonos' a id=DEV_42. Je lance la lecture + notif.",
  "actions": [
    { "kind": "connector", "connector": "spotify", "action": "search",
      "params": { "q": "Bohemian Rhapsody Queen" } },
    { "kind": "connector", "connector": "spotify", "action": "play",
      "params": { "device_id": "DEV_42", "uris": ["spotify:track:..."] } },
    { "kind": "connector", "connector": "pushover", "action": "notify",
      "params": { "title": "Spotify", "message": "Lecture lancee sur Salon Sonos" } },
    { "kind": "finish", "summary": "Track joue sur l enceinte salon + notif envoyee." }
  ],
  "expectedOutcome": "Musique sur enceinte salon + notif mobile."
}

EX 10 — question complexe necessitant une vraie reflexion ("dois-je migrer mon backend Postgres vers une stack event-sourced ?")

Pour les questions de fond qui demandent un raisonnement structure et plusieurs minutes (architecture, stratégie, dilemme produit, debug complexe, refactor majeur), utilise think_long. Cela appelle le modele local Ollama avec une instruction "reflechis a fond" et tu recuperes une analyse longue dans l historique pour synthetiser ensuite.

Plan #1 — declenche la reflexion longue :
{
  "reasoning": "Question architecturale complexe. Je lance think_long pour avoir une analyse structuree (Contexte/Analyse/Recommandation) avant de repondre.",
  "actions": [
    { "kind": "think_long", "topic": "Migration vers event-sourced",
      "prompt": "L user a un backend Postgres CRUD classique avec ~50 tables, 100K users actifs. Il envisage de passer a un modele event-sourced (avec EventStoreDB ou Kafka). Analyse : avantages reels, couts de migration, alternatives intermediaires (CDC, outbox pattern), risques, et recommande une voie precise.",
      "durationHintMs": 240000 }
  ],
  "expectedOutcome": "Analyse longue prete pour synthese."
}
// Plan #2 (apres avoir vu la reflexion dans l historique) :
{
  "reasoning": "L analyse think_long a couvert les avantages (audit trail, replay), les couts (refonte du DAO, formation equipe), et recommande l outbox pattern en transition. Je restitue ca de facon synthetique a l user.",
  "actions": [
    { "kind": "reply", "message": "## Recommandation\n…" },
    { "kind": "finish", "summary": "Reponse architecturale rendue." }
  ],
  "expectedOutcome": "User a une reponse argumentee, courte mais profondement reflechie."
}

QUAND utiliser think_long ?
- Question architecturale, design system, dilemme stratégique
- Debug complexe avec plusieurs hypotheses concurrentes
- Code review qui demande comprehension du contexte global
- Tradeoff non trivial (perf vs lisibilite, simplicite vs flexibilite)

QUAND NE PAS l utiliser ?
- Questions factuelles directes ("quelle heure ?", "compile mon code")
- Taches mecaniques (lancer un commit, ouvrir un fichier)
- Toute action qui peut etre repondue en < 30 secondes

EX 11 — "monitore mon imprimante 3D Bambu pendant le print de cette pièce"
{
  "reasoning": "Print 3D Bambu Lab : statut, progress, temperature.",
  "actions": [
    { "kind": "connector", "connector": "bambu", "action": "list_printers" },
    { "kind": "connector", "connector": "bambu", "action": "get_printer_status",
      "params": { "dev_id": "$first_printer_dev_id" } }
  ],
  "expectedOutcome": "Statut courant rendu, prochaine iter pour synthese si besoin."
}

EX FALLBACK — "analyse cette page" QUAND Aurora-Connect est INSTALLE mais BRIDGE NE LE VOIT PLUS

Si l action browser.analyze_page renvoie "Aucune extension Aurora-Connect detectee" :
NE REINVOQUE PAS browser.* — ca echouera pareil. Bascule sur fetch direct.

Plan #2 (apres echec Plan #1 browser.analyze_page) :
{
  "reasoning": "Aurora-Connect ne repond pas au bridge. Je bascule en fallback fetch HTTP direct ; le digest HTML cote planner extraira title + headings + paragraphs.",
  "actions": [
    { "kind": "fetch", "url": "https://exemple.com/" }
  ],
  "expectedOutcome": "HTML brut recupere, digest pret pour synthese."
}

Plan #3 (synthese basee sur le digest HTML present en historique) :
{
  "reasoning": "Le digest HTML de l historique contient title + headings + paragraphs + links. Je restitue.",
  "actions": [
    { "kind": "reply", "message": "## Page X\n…" },
    { "kind": "finish", "summary": "Analyse rendue via fallback fetch." }
  ],
  "expectedOutcome": "User a sa synthese malgre l extension absente."
}

REGLES CRITIQUES Plan #3 apres fetch :
1. Le PRECEDENT resultat ('digest HTML' dans l historique) contient deja title/headings/paragraphs structures. NE TENTE PAS de re-fetch ou re-parser. Synthetise directement avec un reply markdown.
2. Le JSON DOIT contenir reasoning + actions + expectedOutcome (3 cles obligatoires). Si tu emets juste { actions: [...] }, le parser rejette tout le plan.
3. Le reply.message peut contenir des \\n ; respecte le JSON valide (echappement obligatoire).

EX 12 — "regarde le run #1234 du workflow CI sur main, dis-moi ce qui a foire"
{
  "reasoning": "GitHub Actions debug : list runs, get logs, synthese.",
  "actions": [
    { "kind": "connector", "connector": "github", "action": "list_workflow_runs",
      "params": { "owner": "moi", "repo": "monrepo", "branch": "main" } }
  ],
  "expectedOutcome": "Liste des runs recents recuperee, prochaine iter pour les logs."
}

EX 13 — "remplis ce formulaire/quizz a ma place" (AUTONOMIE FORMS/QUIZZ/CALC)

User te demande de remplir un quizz, un formulaire, un calc en ligne, un sondage. Tu dois agir en autonomate complet :

Plan #1 — analyse la page pour comprendre la structure :
{
  "reasoning": "Lis le formulaire/quizz pour identifier les champs : labels des questions, types (input/textarea/select/radio/checkbox), options possibles, validation patterns, bouton submit.",
  "actions": [
    { "kind": "browser", "operation": "analyze_page" }
  ],
  "expectedOutcome": "Structure du formulaire connue (questions + types + options)."
}

Plan #2 — chaine de browser.fill / browser.click pour chaque champ, en repondant intelligemment a chaque question (math/logique/QCM/texte libre selon le contenu) :
{
  "reasoning": "Le quizz a 5 questions. Question 1 = math (2+3=5), Q2 = QCM 'capitale France' (Paris), Q3 = texte libre (resume contextuel), Q4 = checkbox preferences (tu choisis sur les faits memorises de l user), Q5 = sondage (tu mets une opinion neutre). Puis submit.",
  "actions": [
    { "kind": "browser", "operation": "fill", "payload": { "selector": "input[name=q1]", "value": "5" } },
    { "kind": "browser", "operation": "click", "payload": { "selector": "input[name=q2][value=Paris]" } },
    { "kind": "browser", "operation": "fill", "payload": { "selector": "textarea[name=q3]", "value": "..." } },
    { "kind": "browser", "operation": "click", "payload": { "selector": "input[name=q4_checkbox]" } },
    { "kind": "browser", "operation": "click", "payload": { "selector": "input[name=q5][value=neutre]" } },
    { "kind": "browser", "operation": "click", "payload": { "selector": "button[type=submit]" } },
    { "kind": "reply", "message": "Quizz rempli et soumis. Reponses choisies :\\n- Q1 math : 5\\n- Q2 QCM : Paris\\n- Q3 texte : (resume genere)\\n- Q4 prefs : (basees sur ta memoire)\\n- Q5 sondage : neutre\\n\\nDis-moi si une reponse doit etre changee." },
    { "kind": "finish", "summary": "Quizz autonome rempli." }
  ],
  "expectedOutcome": "Formulaire soumis + recap au user."
}

REGLES forms/quizz :
- Pour les calculs : tu fais le calcul TOI-MEME (ne pas chercher en ligne).
- Pour QCM/factuel : tu reponds avec ta knowledge ou tu chaines fetch perplexity/wikipedia si la question demande info recente.
- Pour preferences : utilise les faits memorises de l user (## Faits memorises plus haut). Si rien de pertinent, demande a l user en reply intermediaire avant de submit.
- Pour text libre : reponds au tonton/format demande, max 2-3 phrases sauf si dissertation explicite.
- TOUJOURS recap les reponses en reply final pour que l user puisse verifier avant de submit irreversible (paiement, envoi mail, etc — dans ce cas demande confirmation explicite).

EX 14 — "j ai besoin de nmap mais il est pas installe" (TOOL AUTO-INSTALL)

Quand un outil necessaire n est pas dispo (shell renvoit "command not found"), tu peux installer le toi-meme via le package manager du systeme :

Plan #1 — detecte l OS + propose installation :
{
  "reasoning": "nmap manque. Detect OS (Linux apt / Mac brew / Windows winget) puis demande confirmation au user pour installer.",
  "actions": [
    { "kind": "shell", "command": "uname", "args": ["-a"] },
    { "kind": "reply", "message": "Pour completer ta tache j ai besoin de **nmap**. Je propose : sudo apt install -y nmap (Linux) ou brew install nmap (Mac). Confirme ? (sinon j abandonne la tache)." },
    { "kind": "finish", "summary": "Demande de confirmation pour install nmap." }
  ],
  "expectedOutcome": "User confirme ou refuse l install."
}

Plan #2 (apres user "ok installe") :
{
  "reasoning": "User a confirme. Install via apt + verify + retry tache initiale.",
  "actions": [
    { "kind": "shell", "command": "sudo", "args": ["apt", "install", "-y", "nmap"] },
    { "kind": "shell", "command": "nmap", "args": ["--version"] }
  ],
  "expectedOutcome": "nmap installe. Prochaine iter : retry la tache initiale."
}

REGLES tool auto-install :
- Detecte les "command not found" / "executable not in PATH" dans les sortes shell.
- Propose TOUJOURS confirmation avant install (apt/brew/yum/dnf/pacman/winget/snap/pip/npm/cargo/go install — destructif modere).
- Pour les outils python : prefere pip install dans un venv ou pipx pour isolation.
- Pour les outils npm globaux : prefere npx (pas d install permanent).
- Apres install, RETRY automatiquement la tache initiale au plan suivant.
- Ne tente pas d installer des kernel modules ou paquets systeme critiques sans escalade explicite.

EX 15 — comprehension-based : "lis cette page et resume / envoie au module Code"

L action browser.analyze_page renvoie maintenant (v82l5+) deux champs derives
purement TOPOLOGIQUES (pas de selecteurs hardcodes site-specific) :

  pageType : { login, article, listing, media, form, dashboard }   // booleens
  signals  : { passwordInputs, formCount, articleTag, videoCount,
               canvasCount, listLikeCount, tableCount, iframeCount }
  iframeTexts : [{ name, length, snippet }]   // same-origin iframes captured

Tu dois te servir de ces signaux pour COMPRENDRE le type de page et choisir
ta strategie sans aucune connaissance prealable du site :

- pageType.login=true ET user demande "connecte-toi" : declenche connector
  autologin si une entree vault existe pour ce hostname, sinon demande creds.
- pageType.article=true : la page est un texte long ; utilise textSnippet
  + paragraphs pour synthetiser, pas besoin de screenshot+vision.
- pageType.listing=true OU tableCount>=1 : la page est un listing ; le
  signal listLikeCount te dit combien d entrees a extraire. Demande au user
  ce qu il veut (filtrer, exporter, comparer).
- pageType.dashboard=true (text-poor + image-rich) : enchaine screenshot +
  vision_describe automatiquement (cf EX 5 auto-vision).
- iframeTexts non vide : la page principale est un shell, le contenu reel
  est dans les iframes ; synthetise sur iframeTexts[*].snippet en priorite.

Quand l user dit "envoie ce que dit cette page au module Code/Conversation/
Cyber/Cinema/3D/Image" :

Plan #1 — lis la page :
{
  "reasoning": "Lecture comprehensive avant de transmettre au module cible.",
  "actions": [
    { "kind": "browser", "operation": "analyze_page" }
  ],
  "expectedOutcome": "Donnees brutes + pageType disponibles pour synthese."
}

Plan #2 — synthese ciblee sur le module destinataire :
{
  "reasoning": "pageType=article, je condense les paragraphs en un brief
                adapte au module Code (focus sur les snippets/specs techniques).",
  "actions": [
    { "kind": "reply", "message": "## Brief pour module Code\\n\\nSource : <url>\\n\\n### Specs detectees\\n- ...\\n\\n### Code present sur la page\\n\`\`\`\\n...\\n\`\`\`\\n\\n### Action proposee\\nVeux-tu que je cree un projet a partir de ca ?" },
    { "kind": "finish", "summary": "Brief module-cible rendu." }
  ],
  "expectedOutcome": "User a un brief deja formate pour le module destinataire."
}

REGLE CRITIQUE — pas de hardcoded selectors :
NE JAMAIS supposer un selecteur de classe specifique a un site (\`.foo-grade\`,
\`#pronote-notes\`, \`.bambu-status\`). Tu travailles UNIQUEMENT sur :
  - signaux topologiques (compteurs, structure)
  - texte (textSnippet, paragraphs, iframeTexts[].snippet)
  - meta tags et OG (deja extraits)
  - vision_describe sur screenshot si la page est text-poor
La comprehension du contenu se fait par ton reasoning + le LLM, jamais via
des regles "site X = selecteur Y".

EX 16 — comprehension-based extraction via browser.extract_structured (v82l6+) :

Quand l user veut une LISTE STRUCTUREE depuis une page (cours, prix, messages,
articles, contacts, releves bancaires, devoirs, evenements...) au lieu de
recoller toi-meme du texte dans Plan #2, tu peux deleguer l extraction a un
LLM local via :
  { kind:"browser", operation:"extract_structured", payload:{ intent:"<phrase libre>" } }

Le bridge appelle Ollama (qwen3:14b par default, qwen3-vl:8b si includeImage=true)
avec un system prompt qui force du JSON. Le LLM choisit lui-meme le schema des
items en fonction de l intent — tu n as aucun selecteur a fournir, aucune
structure a definir.

Exemple Plan #1 + Plan #2 :

Plan #1 (lis + extrait) :
{
  "reasoning": "User veut la liste des cours d aujourd hui. analyze_page d abord pour le pageType, puis extract_structured avec un intent precis.",
  "actions": [
    { "kind": "browser", "operation": "analyze_page" },
    { "kind": "browser", "operation": "extract_structured", "payload": { "intent": "liste des cours du jour avec heure de debut, heure de fin, matiere, salle, prof" } }
  ],
  "expectedOutcome": "items[] avec schema cours pret pour synthese."
}

Plan #2 (synthese) :
{
  "reasoning": "Restitue les cours dans un tableau markdown lisible.",
  "actions": [
    { "kind": "reply", "message": "## Tes cours aujourd hui\\n\\n| Heure | Matiere | Salle | Prof |\\n|---|---|---|---|\\n| ..." },
    { "kind": "finish", "summary": "Cours du jour rendus." }
  ],
  "expectedOutcome": "User a son emploi du temps formate."
}

Quand utiliser extract_structured plutot que synthetiser toi-meme ?
- Listings repetitifs (>=5 entrees du meme schema) : oui, gain de fiabilite.
- Pages text-poor avec layout visuel (dashboards, infographies) : ajoute
  includeImage:true pour basculer sur qwen3-vl.
- Texte dense non structure (article, mail) : non, repli sur reply direct.

EX 17 — auto-bascule includeImage:true (vision) selon les signaux topologiques (v82l9+) :

Quand tu plannifies un extract_structured APRES un analyze_page, tu DOIS
inspecter pageType + signals dans l historique pour decider si la page est
fondamentalement graphique. Dans ce cas, ajoute \`includeImage: true\` au
payload pour basculer le bridge sur qwen3-vl:8b — le scraping texte rate
les semantiques visuelles (cartes de produit, dashboards de KPI, viewers
embedded, schemas, infographies). C est ta DECISION, pas une regle codee :
les criteres ci-dessous sont des heuristiques que TU evalues sur le
resultat de analyze_page.

Heuristiques (ANY of) :
  - pageType.media === true                                 (canvas/video lourd)
  - pageType.dashboard === true ET signals.imgCount >= 3    (dashboard riche en images)
  - signals.iframeCount >= 1 ET signals.textLength < 600    (viewer iframe-based,
    texte principal vide)

Aucun selecteur hardcode. Aucune liste de domaines. Tu lis les signaux
deja collectes par analyze_page (cf EX 15) et tu decides.

Plan #1 (analyze first) :
{
  "reasoning": "User veut extraire les KPI de cette page. Lance analyze_page d abord pour decider si vision est utile.",
  "actions": [
    { "kind": "browser", "operation": "analyze_page" }
  ],
  "expectedOutcome": "Topologie connue ; je deciderai apres si extract_structured a besoin d includeImage."
}

Plan #2 (le resultat analyze_page montre pageType.dashboard=true, signals.imgCount=8) :
{
  "reasoning": "Dashboard avec 8 images — le scraping texte rate la semantique visuelle. Bascule en vision.",
  "actions": [
    { "kind": "browser", "operation": "extract_structured", "payload": { "intent": "liste KPI avec valeur et delta", "includeImage": true } }
  ],
  "expectedOutcome": "items[] avec KPI tirees du visuel via qwen3-vl."
}

Plan #2 alternatif (analyze_page revele pageType.article=true) :
{
  "reasoning": "Article texte dense — pas de vision necessaire, le scraping suffit.",
  "actions": [
    { "kind": "browser", "operation": "extract_structured", "payload": { "intent": "principales entites mentionnees" } }
  ],
  "expectedOutcome": "items[] avec entites depuis le texte (qwen3:14b text-only)."
}

ANTI-PATTERN : ne mets JAMAIS includeImage:true par reflexe. Surcout latence
+ bande passante. Ne l active QUE si une heuristique ci-dessus est satisfaite.

EX 18 — pageType.social_feed → mode=card_iteration auto (v82ly+) :

Quand analyze_page revele pageType.social_feed=true (>=3 des 4 signaux :
repeating_card_count>=5, avatars>=2, timestamps relatifs, reaction_buttons>=2)
TU DOIS chainer extract_structured avec mode=card_iteration au plan suivant.
La mecanique : le bridge enrichit alors son system prompt LLM pour emettre UN
item par carte (auteur, date_relative, contenu, reactions) au lieu d un blob.

Important — ZERO selecteur hardcode site-specific. Tu propages juste les
signaux topologiques mesures par analyze_page : repeating_card_count,
has_avatars, has_timestamps, has_reactions. Le LLM downstream lit ces hints
et structure sa sortie.

Plan #1 (analyze first) :
{
  "reasoning": "User veut comprendre ce feed. analyze_page d abord pour confirmer la topologie sociale_feed avant extraction.",
  "actions": [
    { "kind": "browser", "operation": "analyze_page" }
  ],
  "expectedOutcome": "Topologie connue ; si social_feed=true je chaine card_iteration."
}

Plan #2 (analyze_page revele pageType.social_feed=true, signals.listLikeCount=12, avatars=8, timestamps=true, reactions=24) :
{
  "reasoning": "social_feed confirme (4 signaux sur 4). Bascule en card_iteration : 1 item par carte avec auteur/date/contenu/reactions.",
  "actions": [
    { "kind": "browser", "operation": "extract_structured", "payload": {
        "intent": "extract recent posts from this social feed",
        "mode": "card_iteration",
        "card_signals": { "repeating_card_count": 12, "has_avatars": true, "has_timestamps": true, "has_reactions": true }
    } }
  ],
  "expectedOutcome": "items[] avec une entree par post (auteur/date/contenu/reactions)."
}

Plan #3 (synthese apres reception items) :
{
  "reasoning": "Restitue les posts dans une liste markdown lisible. Cite les auteurs et dates.",
  "actions": [
    { "kind": "reply", "message": "## Feed recent (N posts)\\n\\n- **<auteur1>** — il y a 2h\\n  > <contenu>\\n  *<reactions> reactions*\\n- ..." },
    { "kind": "finish", "summary": "Feed restitue." }
  ],
  "expectedOutcome": "User a un resume du feed avec attribution par carte."
}

Si pageType.social_feed=false : NE BASCULE PAS en card_iteration. Garde une
extraction libre (intent: "<phrase>") sans mode special. card_iteration n a
de sens QUE pour les feeds de cartes repetitives type LinkedIn/Twitter/feed
de discussions GitHub. Un article long, un dashboard, une page produit ne
rentrent PAS dans le pattern.

NOTE : un post-processeur deterministe injectera AUTOMATIQUEMENT cette
chaine en Plan #2 si tu oublies de l emettre — mais sois explicite quand
meme, ca evite des aller-retours.

EX 19 — pageType.article_quality (v82n0+) :

Le champ pageType.article_quality est rempli par analyze_page (4 valeurs :
"rich", "thin", "paywall", "unknown"). Topologie pure, AUCUN selecteur en dur.

  - rich    : article tag + texte >1500c + >=2 paragraphes longs + heading ;
              le scrape suffit, fais une synthese directe en Plan #2.
  - thin    : article tag mais texte <800c — souvent un teaser/landing.
              N envoie pas de markdown structure (rien a structurer) ; demande
              clarification au user OU enchaine vers une page detail visible.
  - paywall : overlay >60% de la viewport avec termes auth/abonn/subscri.
              Mentionne dans le reply que la page est un paywall et suggere
              une extension type "Bypass Paywalls Clean" ou archive.is.
              N invente PAS le contenu derriere le paywall.
  - unknown : autre. Comporte-toi comme avant.

EX 20 — listingSubtype (v82n0+) :

Le champ signals.listingSubtype classe les listings non-feeds en 4 sous-types :
  - search_results  : >=8 items avec heading + lien + snippet
  - product_listing : >=3 items avec pattern de prix (€/$/£ + chiffres)
  - news_listing    : >=3 items avec date + author-like signature
  - generic         : listing sans signal subtype distinctif

Sur un listing rich (search/product/news), un post-processeur injecte
AUTOMATIQUEMENT une extract_structured(card_iteration) avec un intent adapte
(ex pour product : "extract products with name, price, currency, rating if any").
Tu peux aussi l emettre toi-meme dans Plan #2 si tu prefers.
`.trim()

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export type PlannerContext = {
  userPrompt: string
  runtime: CoworkRuntime
  capabilities: CoworkCapability[]
  workspaceRoot: string
  // v82m0 — entries can carry the optional `under_extraction` flag annotated
  // by the orchestrator after a successful card_iteration extract whose item
  // count fell below half the cards_processed count. Surfaced in the user
  // prompt history block so the LLM can naturally retry with includeImage:true.
  // v82m6 — entries can also carry an optional `delta_history` array (the
  // last <=5 host-yield deltas in pp) so `buildVisualRetryNudge` can detect
  // a sustained downward trajectory and emit the tier-2 DUAL_SIGNAL_TREND
  // nudge instead of the one-shot DUAL_SIGNAL hint.
  history: Array<{
    action: CoworkAction
    result: CoworkActionResult
    under_extraction?: boolean
    reason?: string
    delta_history?: number[]
  }>
  signal?: AbortSignal
  // Active module — adds module-specific context to the system prompt.
  module?: ModuleId
  // Voice mode → use the voice-specific system prompt (1-2 short sentences).
  voiceMode?: boolean
  // v21 — conversation continuity : prior user/Aurora exchanges from the
  // chat overlay (max ~5 turns), injected into the system prompt so
  // follow-up questions can implicitly reference earlier context.
  conversationHistory?: Array<{ role: 'user' | 'aurora'; content: string }>
  // v29 — image descriptions : the overlay pre-ran vision_describe on user-
  // attached images and passes the textual descriptions here. Surfaced in
  // the system prompt so the planner can synthesise without re-running
  // vision. Cap to 3 descriptions to keep the prompt compact.
  attachedImageDescriptions?: string[]
  // Project thread: generated artifacts, active reference, version chain and
  // previous multi-module steps extracted from the Cowork chat.
  projectThread?: CoworkProjectThread
  // v82m6 — user-pinned connectors. When non-empty, the planner emits a
  // single-line [USER_PROMOTED] hint listing the connector ids so the LLM
  // can prefer their dedicated actions over generic open_url/extract_structured
  // when the host matches. Empty / undefined → ZERO token overhead (no line
  // appended).
  pinnedConnectorIds?: string[]
  // v82m6 — hosts on which the dual-signal nudge has been INEFFECTIVE
  // (>= 5 emitted, 0 accepted per the bridge `dual-signal-effective`
  // endpoint). When the current host appears, the planner emits the
  // DUAL_SIGNAL_INEFFECTIVE fallback hint suggesting a strategy change
  // instead of repeating the screenshot+includeImage path.
  ineffectiveHosts?: string[]
  // v82m8 — hosts on which the tier-2 DUAL_SIGNAL_TREND nudge has also
  // been INEFFECTIVE (>= 3 emitted, 0 accepted per
  // `trend-signal-stats`). When BOTH tiers are ineffective on the same
  // host, the planner escalates to the terminal TIER_3 nudge (manual
  // review). Single ineffective tier preserves the existing fallback hint.
  trendIneffectiveHosts?: string[]
}

export async function planNextStep(ctx: PlannerContext): Promise<CoworkPlan> {
  const deterministic = buildDeterministicPlan(ctx)
  if (deterministic) return deterministic
  // Accompagnement (coaching / organisation / planification / conseil / soutien).
  // Un petit modele local se perd dans le gigantesque prompt cowork et retombe
  // sur son reflexe "je pose des questions". On le court-circuite par une SEULE
  // generation FOCALISEE qui livre un plan concret structure (cf. coworkConversation
  // mode=accompagnement). Continuite preservee : on injecte conversation + memoire.
  const accompaniment = await buildAccompanimentPlan(ctx)
  if (accompaniment) return accompaniment
  const sys = buildSystemPrompt(ctx)
  const user = buildUserPrompt(ctx)
  return planWithRetry(sys, user, 2, ctx.signal, ctx)
}

// Focused coaching generation. Returns null unless this is the FIRST turn of an
// accompaniment request — multi-step / tool-augmented continuations ("oui cree
// le fichier", "ajoute les dates officielles") fall through to the normal
// agentic planner.
async function buildAccompanimentPlan(ctx: PlannerContext): Promise<CoworkPlan | null> {
  const frame = resolveCoworkConversationFrame(ctx.userPrompt, ctx.conversationHistory)
  if (frame.mode !== 'accompagnement') return null
  if (ctx.history.length > 0) return null

  const settings = loadSettings()
  const memory = settings.userMemory.slice(-12).map((e) => `- ${e.fact}`).join('\n')
  const recent = (ctx.conversationHistory ?? []).slice(-6)
    .map((t) => `[${t.role === 'user' ? 'USER' : 'AURORA'}] ${(t.content || '').replace(/\s+/g, ' ').slice(0, 400)}`)
    .join('\n')

  const focusedSystem = [
    'Tu es Aurora, un coach/copilote francophone bienveillant et concret.',
    "L utilisateur demande de l ACCOMPAGNEMENT (s organiser, planifier, se preparer, decider, etre soutenu).",
    'Ton job : livrer IMMEDIATEMENT un livrable exploitable, pas une discussion.',
    '',
    'REGLES IMPERATIVES :',
    "- INTERDIT de commencer par une question ou par 'pour t aider j ai besoin de...'.",
    "- Si une info manque, ENONCE une hypothese raisonnable en une ligne puis continue.",
    '- Produis un PLAN concret et structure en markdown : titres (##), listes, et un decoupage par jour/creneau ou par etapes avec priorites, durees ou echeances, et un bref pourquoi.',
    '- Sois SPECIFIQUE et personnalise (utilise le contexte et la memoire ci-dessous). Pas de generalites creuses, pas de disclaimer du type "ceci est un exemple, adapte-le".',
    "- Termine par une section '## Prochaine etape' proposant UNE action concrete de suivi (ex : 'je te cree ce planning en fichier .md', 'je te mets des rappels'), et AU PLUS une seule question ciblee, seulement si une hypothese erronee couterait cher.",
    memory ? `\nMemoire sur l utilisateur (a exploiter) :\n${memory}` : '',
    recent ? `\nConversation recente (continuite) :\n${recent}` : '',
  ].filter(Boolean).join('\n')

  try {
    const model = useAppStore.getState().mainModel
    const response = await ollamaChat(
      model,
      [
        { role: 'system', content: focusedSystem },
        { role: 'user', content: ctx.userPrompt },
      ],
      undefined,
      { signal: ctx.signal, num_ctx: 32000, firstByteTimeoutMs: 900_000 },
    )
    const text = extractContent(response).trim()
    if (!text || text.length < 80) return null

    const actions: CoworkAction[] = [{ kind: 'reply', message: text }]
    if (ctx.voiceMode) {
      const spoken = text.replace(/[#*_`>|-]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 240)
      actions.push({ kind: 'voice_speak', text: spoken })
    }
    actions.push({ kind: 'finish', summary: 'Plan d accompagnement livre.' })
    return {
      reasoning: 'Demande d accompagnement : je livre directement un plan concret et structure (generation focalisee), avec une proposition de suivi.',
      actions,
      expectedOutcome: 'L utilisateur recoit un plan exploitable et une prochaine etape concrete, sans interrogatoire.',
    }
  } catch {
    // Le modele a echoue → on laisse le planner standard prendre le relais.
    return null
  }
}

function buildDeterministicPlan(ctx: PlannerContext): CoworkPlan | null {
  const desktopPlan = buildDesktopDeterministicPlan(ctx)
  if (desktopPlan) return desktopPlan
  const userFolderFilterPlan = buildUserFolderFilteredListingPlan(ctx)
  if (userFolderFilterPlan) return userFolderFilterPlan
  const userFolderOverviewPlan = buildUserFolderOverviewPlan(ctx)
  if (userFolderOverviewPlan) return userFolderOverviewPlan
  const userFolderPlan = buildUserFolderArtifactPlan(ctx)
  if (userFolderPlan) return userFolderPlan
  const academicWebPlan = buildAcademicWebResearchPlan(ctx)
  if (academicWebPlan) return academicWebPlan
  const creativeProductionPlan = buildCreativeProductionPlan(ctx)
  if (creativeProductionPlan) return creativeProductionPlan
  const workspacePlan = buildWorkspaceExplorationPlan(ctx)
  if (workspacePlan) return workspacePlan
  const missionBootstrapPlan = buildMissionBootstrapPlan(ctx)
  if (missionBootstrapPlan) return missionBootstrapPlan
  const creativePlan = buildCreativeReflectionPlan(ctx)
  if (creativePlan) return creativePlan
  return null
}

function buildMissionBootstrapPlan(ctx: PlannerContext): CoworkPlan | null {
  const frame = resolveCoworkConversationFrame(ctx.userPrompt, ctx.conversationHistory)
  if (!frame.shouldExecute) return null
  const profile = classifyCoworkMission(frame.effectivePrompt)

  if (profile.kind === 'code' || profile.kind === 'debug') {
    const inventory = findLatestWorkspaceInventory(ctx.history)
    if (!inventory && ctx.runtime === 'tauri-desktop') {
      return {
        reasoning: 'Le message demande un vrai travail logiciel. Je commence par cartographier le workspace au lieu de repondre sans observer le code.',
        actions: [
          {
            kind: 'think',
            topic: 'mission logicielle cowork',
            thought: `Objectif effectif: ${frame.effectivePrompt}. Je vais inventorier, lire les pivots, modifier si necessaire, puis tester.`,
          },
          buildWorkspaceInventoryShellAction(ctx.workspaceRoot),
        ],
        expectedOutcome: 'Aurora obtient la carte du projet pour lire les bons fichiers avant de corriger ou ameliorer.',
      }
    }

    if (inventory) {
      const unread = selectWorkspaceFilesForReading(inventory.result.output || '', frame.effectivePrompt)
        .filter((path) => !hasReadWorkspacePath(ctx.history, path))
        .slice(0, 8)
      if (unread.length > 0 && countWorkspaceReadActions(ctx.history) < 16) {
        return {
          reasoning: 'Le workspace est cartographie. Je lis les fichiers pivots lies a la mission avant de modifier quoi que ce soit.',
          actions: unread.map((path) => ({ kind: 'read_file', path })),
          expectedOutcome: 'Aurora dispose du contenu utile pour executer la demande au lieu de rester en surface.',
        }
      }
    }

    const continuation = buildImplementationContinuationPlan(ctx, frame)
    if (continuation) return continuation
  }

  if (profile.kind === 'research' && !ctx.history.some((entry) => entry.action.kind === 'web_search')) {
    return {
      reasoning: 'La mission demande une recherche. Je lance une recherche native avant toute synthese.',
      actions: [
        {
          kind: 'think',
          topic: 'recherche active',
          thought: `Je traite la demande comme une recherche a executer: ${frame.effectivePrompt}`,
        },
        {
          kind: 'web_search',
          query: frame.effectivePrompt.slice(0, 240),
          limit: 6,
        },
      ],
      expectedOutcome: 'Aurora obtient des resultats consultables pour enchainer sur fetch ou synthese.',
    }
  }

  return null
}

function buildImplementationContinuationPlan(
  ctx: PlannerContext,
  frame: CoworkConversationFrame,
): CoworkPlan | null {
  if (!isImplementationDemand(frame.effectivePrompt)) return null
  const hasObservation = ctx.history.some((entry) => entry.result.ok && ['read_file', 'list_dir', 'shell', 'fetch', 'web_search', 'browser', 'connector'].includes(entry.action.kind))
  const hasMutation = ctx.history.some((entry) => entry.result.ok && ['write_file', 'edit_file', 'delete_file'].includes(entry.action.kind))
  const alreadyReflected = ctx.history.some((entry) => entry.action.kind === 'think_long' && /execution/.test(entry.action.topic))
  if (!hasObservation || hasMutation || alreadyReflected) return null

  return {
    reasoning: 'Les fichiers ont ete observes mais aucune correction n a encore ete appliquee. Je force une reflexion operationnelle avant de laisser le planner produire les edits.',
    actions: [
      {
        kind: 'think_long',
        topic: 'strategie execution cowork',
        prompt: [
          'Objectif utilisateur effectif :',
          frame.effectivePrompt,
          '',
          'Historique observe :',
          summarizeHistoryForExecution(ctx.history),
          '',
          'Trouve les modifications concretes a appliquer, les fichiers probables, le test de verification, et les risques. Ne produis pas une simple discussion.',
        ].join('\n'),
        durationHintMs: 180_000,
      },
    ],
    expectedOutcome: 'Aurora obtient une strategie de correction concrete avant edition et verification.',
  }
}

function isImplementationDemand(prompt: string): boolean {
  const current = normalizeIntentText(prompt)
  const wantsChange = /\b(corrige|corriger|fix|debug|ameliore|ameliorer|modifie|modifier|implemente|implementer|applique|appliquer|cree|creer|genere|generer|reprends|reprendre|refactor|teste|tester|verifie|verifier)\b/.test(current)
  const targetsProject = /\b(code|repo|projet|workspace|application|app|tauri|desktop|module|cowork|service|component|composant|test|build|typescript|javascript|rust|python|css|ui|interface)\b/.test(current)
  return wantsChange && targetsProject
}

function summarizeHistoryForExecution(history: PlannerContext['history']): string {
  return history
    .slice(-12)
    .map((entry, index) => {
      const action = summarizeActionForExecution(entry.action)
      const status = entry.result.ok ? 'OK' : 'KO'
      const output = (entry.result.output || entry.result.error || '').replace(/\s+/g, ' ').trim().slice(0, 420)
      return `${index + 1}. ${action} -> ${status}${output ? ` : ${output}` : ''}`
    })
    .join('\n')
}

function summarizeActionForExecution(action: CoworkAction): string {
  switch (action.kind) {
    case 'read_file':
    case 'list_dir':
    case 'write_file':
    case 'delete_file':
      return `${action.kind} ${action.path}`
    case 'edit_file':
      return `edit_file ${action.path}`
    case 'shell':
      return `shell ${action.command} ${(action.args || []).join(' ')}`.trim()
    case 'web_search':
      return `web_search ${action.query}`
    case 'fetch':
      return `fetch ${action.url}`
    case 'browser':
      return `browser ${action.operation}`
    case 'connector':
      return `connector ${action.connector}.${action.action}`
    case 'think':
    case 'think_long':
      return `${action.kind} ${action.topic}`
    default:
      return action.kind
  }
}

function buildDesktopDeterministicPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isDesktopAnalysisRequest(ctx)) return null
  if (ctx.history.length > 0) {
    const reply = buildDesktopAnalysisReply(ctx.history)
    if (reply) {
      return {
        reasoning: 'Les donnees systeme sont deja collectees. Je produis la fiche sans demander a l utilisateur de valider la capture.',
        actions: [
          { kind: 'reply', message: reply },
          { kind: 'finish', summary: 'Fiche systeme et bureau produite.' },
        ],
        expectedOutcome: 'L utilisateur recoit une fiche recapitulant son systeme, son bureau et les elements observes.',
      }
    }
    const failedInventoryAttempts = countDesktopInventoryShellFailures(ctx.history)
    if (failedInventoryAttempts >= 2) {
      const partial = buildDesktopPartialReply(ctx.history)
      if (partial) {
        return {
          reasoning: 'Deux collectes systeme ont echoue. Je finalise avec les donnees observables au lieu de boucler sur la meme commande.',
          actions: [
            { kind: 'reply', message: partial },
            { kind: 'finish', summary: 'Fiche partielle produite apres recuperation.' },
          ],
          expectedOutcome: 'L utilisateur recoit une fiche exploitable et les erreurs techniques utiles pour la suite.',
        }
      }
    }
    if (ctx.runtime === 'tauri-desktop') {
      return {
        reasoning: failedInventoryAttempts > 0
          ? 'La premiere collecte systeme a echoue. Je relance avec une sortie PowerShell UTF-8 structuree au lieu de repeter exactement la meme commande.'
          : 'La capture seule ne suffit pas. Je collecte maintenant les donnees systeme textuelles pour produire la fiche.',
        actions: [buildDesktopInventoryShellAction(failedInventoryAttempts > 0 ? 'utf8_retry' : 'standard')],
        expectedOutcome: 'Aurora obtient les informations systeme necessaires pour synthetiser.',
      }
    }
    return null
  }
  if (ctx.runtime !== 'tauri-desktop') {
    return {
      reasoning: 'La demande vise le bureau informatique, mais le runtime courant ne donne pas accès au shell système. Je collecte ce qui reste accessible.',
      actions: [
        { kind: 'browser', operation: 'screenshot' },
      ],
      expectedOutcome: 'Aurora obtient au moins une capture visuelle avant de synthétiser.',
    }
  }

  return {
    reasoning: 'La demande concerne le bureau informatique. Je collecte directement les informations systeme, les applications actives, le contenu du Bureau et une capture ecran.',
    actions: [
      { kind: 'screenshot_desktop', quality: 'fast', display: 'primary' },
      buildDesktopInventoryShellAction('standard'),
    ],
    expectedOutcome: 'Aurora dispose des donnees necessaires pour produire une fiche recapitulatif complete au tour suivant.',
  }
}

function buildUserFolderOverviewPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isUserFolderOverviewRequest(ctx)) return null
  const target = resolveUserFolderTarget(ctx)
  if (!target) return null

  const listing = findLatestListDirForPath(ctx.history, target.path)
  if (!listing) {
    return {
      reasoning: `Le dernier message demande un topo du dossier ${target.label}. Je scanne ce dossier utilisateur sans reprendre l ancienne creation de document.`,
      actions: [
        {
          kind: 'think',
          topic: 'topo dossier utilisateur',
          thought: `Objectif courant : faire un topo du contenu de ${target.path}. La conversation precedente peut expliquer pourquoi ce dossier interesse l user, mais je ne dois pas recreer le PDF precedent.`,
        },
        { kind: 'list_dir', path: target.path, depth: 2 },
      ],
      expectedOutcome: 'Aurora obtient la liste du dossier utilisateur pour produire un topo.',
    }
  }

  const reply = buildUserFolderOverviewReply(target, listing.result.output || '')
  return {
    reasoning: 'Le dossier utilisateur a ete liste. Je produis un topo clair au lieu de creer un fichier non demande.',
    actions: [
      { kind: 'reply', message: reply },
      { kind: 'finish', summary: `Topo du dossier ${target.label} produit.` },
    ],
    expectedOutcome: 'L utilisateur recoit une synthese des fichiers et dossiers du dossier cible.',
  }
}

function buildUserFolderArtifactPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isUserFolderArtifactRequest(ctx)) return null
  const target = resolveUserFolderTarget(ctx)
  if (!target) return null

  const artifact = buildRequestedArtifactDescriptor(ctx, target.path)
  const primaryVerified = findLatestSuccessfulRead(ctx.history, artifact.path)
  const primaryWritten = findLatestActionForPath(ctx.history, 'write_file', artifact.path)
  const fallbackVerified = findLatestSuccessfulRead(ctx.history, artifact.fallbackPath)
  const fallbackWritten = findLatestActionForPath(ctx.history, 'write_file', artifact.fallbackPath)
  const completedPath = primaryWritten?.result.ok && primaryVerified?.result.ok
    ? artifact.path
    : (fallbackWritten?.result.ok && fallbackVerified?.result.ok ? artifact.fallbackPath : null)
  if (completedPath) {
    return {
      reasoning: 'Le dossier utilisateur a ete scanne, le PDF a ete cree puis relu. Je peux finaliser avec un chemin verifie.',
      actions: [
        {
          kind: 'reply',
          message: [
            `C est fait : j ai scanne le dossier ${target.label}, cree le PDF et verifie qu il est lisible.`,
            '',
            `Fichier : \`${completedPath}\``,
            '',
            'Le document contient une fiche de revision structuree avec dates, causes, grandes phases, France, Shoah, consequences, vocabulaire et methode pour le controle.',
          ].join('\n'),
        },
        { kind: 'finish', summary: `PDF cree et verifie dans ${target.label}.` },
      ],
      expectedOutcome: 'L utilisateur dispose du PDF dans le dossier demande, avec verification locale.',
    }
  }

  if (primaryWritten?.result.ok && !primaryVerified) {
    return {
      reasoning: 'Le PDF a ete ecrit. Je le relis maintenant avant de finaliser, pour eviter de promettre un fichier non verifie.',
      actions: [{ kind: 'read_file', path: artifact.path }],
      expectedOutcome: 'Aurora confirme que le fichier PDF existe et contient une structure PDF lisible.',
    }
  }
  if (fallbackWritten?.result.ok && !fallbackVerified) {
    return {
      reasoning: 'Le PDF de secours a ete ecrit. Je le relis maintenant avant de finaliser.',
      actions: [{ kind: 'read_file', path: artifact.fallbackPath }],
      expectedOutcome: 'Aurora confirme que le fichier PDF de secours existe.',
    }
  }

  const listing = findLatestListDirForPath(ctx.history, target.path)
  if (!listing) {
    return {
      reasoning: `La demande cible ${target.label}, pas le workspace du projet. Je commence par scanner ce dossier utilisateur avant de creer le PDF.`,
      actions: [
        {
          kind: 'think',
          topic: 'dossier utilisateur',
          thought: `Je traite "${target.label}" comme un dossier utilisateur local (${target.path}). Je vais le scanner, lire les notes pertinentes si elles existent, creer le PDF dans ce dossier, puis verifier le fichier.`,
        },
        { kind: 'list_dir', path: target.path, depth: 2 },
      ],
      expectedOutcome: 'Aurora obtient la liste des fichiers du dossier utilisateur demande.',
    }
  }

  const unread = selectUserFolderReadableFiles(listing.result.output || '', target.path, getEffectiveUserPrompt(ctx))
    .filter((path) => !hasReadWorkspacePath(ctx.history, path))
    .slice(0, 6)
  if (unread.length > 0 && countWorkspaceReadActions(ctx.history) < 12) {
    return {
      reasoning: 'Le dossier utilisateur est scanne. Je lis les fichiers texte probablement utiles avant de produire le PDF.',
      actions: unread.map((path) => ({ kind: 'read_file', path })),
      expectedOutcome: 'Aurora recupere les notes locales pertinentes pour enrichir le document.',
    }
  }

  const failedWrites = ctx.history.filter((entry) => (
    entry.action.kind === 'write_file'
    && normalizeWorkspacePath(entry.action.path).toLowerCase() === normalizeWorkspacePath(artifact.path).toLowerCase()
    && !entry.result.ok
  )).length
  const outputPath = failedWrites > 0 ? artifact.fallbackPath : artifact.path
  const pdf = buildStudyPdfContent(ctx, target, listing, outputPath)
  return {
    reasoning: failedWrites > 0
      ? 'La premiere ecriture du PDF a echoue. Je retente avec un nom de fichier plus simple dans le meme dossier.'
      : 'Le dossier utilisateur a ete scanne. Je cree maintenant un vrai fichier PDF texte, puis je le relirai au tour suivant.',
    actions: [
      { kind: 'write_file', path: outputPath, content: pdf },
      { kind: 'read_file', path: outputPath },
    ],
    expectedOutcome: 'Aurora cree le PDF dans le dossier demande et verifie immediatement sa presence.',
  }
}

function buildWorkspaceExplorationPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isWorkspaceExplorationRequest(ctx)) return null

  const inventory = findLatestWorkspaceInventory(ctx.history)
  if (!inventory) {
    const failedInventory = countWorkspaceInventoryFailures(ctx.history)
    if (failedInventory > 0) {
      return {
        reasoning: 'L inventaire rg --files a echoue. Je bascule sur une liste de dossier pour ne pas bloquer la navigation workspace.',
        actions: [
          { kind: 'list_dir', path: ctx.workspaceRoot || '.', depth: 3 },
        ],
        expectedOutcome: 'Aurora obtient au moins une arborescence de secours avant de continuer.',
      }
    }
    return {
      reasoning: 'La demande vise le projet ou tous les fichiers. Je commence par cartographier le workspace avant de lire ou modifier quoi que ce soit.',
      actions: [
        {
          kind: 'think',
          topic: 'strategie workspace',
          thought: 'Je vais d abord inventorier les fichiers, exclure les dossiers generes, lire les pivots, puis agir ou synthetiser selon la demande.',
        },
        buildWorkspaceInventoryShellAction(ctx.workspaceRoot),
      ],
      expectedOutcome: 'Aurora obtient la carte des fichiers du workspace pour choisir les bons fichiers a lire.',
    }
  }

  const selectedPaths = selectWorkspaceFilesForReading(inventory.result.output || '', getEffectiveUserPrompt(ctx))
  const unread = selectedPaths
    .filter((path) => !hasReadWorkspacePath(ctx.history, path))
    .slice(0, 8)

  if (unread.length > 0 && countWorkspaceReadActions(ctx.history) < 16) {
    return {
      reasoning: 'L inventaire est disponible. Je lis maintenant les fichiers pivots au lieu de demander a l utilisateur quoi ouvrir.',
      actions: unread.map((path) => ({ kind: 'read_file', path })),
      expectedOutcome: 'Aurora dispose du contenu utile des fichiers principaux pour raisonner et agir.',
    }
  }

  if (isCreativeApplyRequest(ctx)) {
    return null
  }

  const reply = buildWorkspaceExplorationReply(ctx, inventory)
  if (!reply) return null
  return {
    reasoning: 'Les fichiers pivots ont ete lus. Je rends une carte exploitable du workspace avec les prochaines actions possibles.',
    actions: [
      { kind: 'reply', message: reply },
      { kind: 'finish', summary: 'Exploration workspace synthetisee.' },
    ],
    expectedOutcome: 'L utilisateur recoit une synthese claire du projet et des fichiers explores.',
  }
}

function buildCreativeReflectionPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isCreativeReflectionRequest(ctx)) return null
  if (ctx.history.some((entry) => entry.action.kind === 'think_long' || (entry.action.kind === 'think' && /creativ/i.test(entry.action.topic)))) {
    return null
  }
  return {
    reasoning: 'La demande est creative/strategique. Je lance une reflexion longue avant de proposer ou produire le resultat final.',
    actions: [
      {
        kind: 'think_long',
        topic: 'exploration creative',
        prompt: [
          'Demande utilisateur exacte :',
          getEffectiveUserPrompt(ctx).trim(),
          '',
          'Travaille comme un copilote creatif local : clarifie l objectif implicite, propose plusieurs directions, choisis la meilleure hypothese par defaut, liste les risques/contraintes, puis recommande un plan concret a appliquer. Si un artefact peut etre produit, indique quoi produire et comment verifier le resultat.',
        ].join('\n'),
        durationHintMs: 180_000,
      },
    ],
    expectedOutcome: 'Aurora obtient une reflexion structuree pour produire une reponse ou une action plus ambitieuse au tour suivant.',
  }
}

type CreativeProductionKind = 'image' | 'model3d' | 'game' | 'code' | 'video' | 'audio'

type CreativeProductionIntent = {
  kind: CreativeProductionKind
  connector: string
  action: string
  prompt: string
  needsReferenceSearch: boolean
  language?: string
}

function buildCreativeProductionPlan(ctx: PlannerContext): CoworkPlan | null {
  const intent = classifyCreativeProductionIntent(ctx)
  if (!intent) return null

  const latest = findLatestCreativeConnectorEntry(ctx, intent)
  if (latest?.result.ok) {
    return {
      reasoning: 'Le module de generation a retourne un resultat. Je finalise avec le chemin et les actions utilisateur disponibles dans la conversation.',
      actions: [
        { kind: 'reply', message: buildCreativeProductionReply(ctx, intent, latest) },
        { kind: 'finish', summary: `${creativeKindLabel(intent.kind)} genere et reference dans le fil Cowork.` },
      ],
      expectedOutcome: 'L utilisateur voit le resultat, son chemin et les boutons de consultation/telechargement dans la conversation.',
    }
  }

  const failures = findCreativeConnectorFailures(ctx, intent)
  const retriedWithoutResearch = ctx.history.some((entry) =>
    entry.action.kind === 'connector'
    && entry.action.connector === intent.connector
    && (entry.action.params as Record<string, unknown> | undefined)?.no_research === true,
  )
  if (failures.length > 0 && intent.kind === 'image' && !retriedWithoutResearch) {
    return {
      reasoning: 'La premiere generation image a echoue. Je tente une seconde passe plus robuste sans recherche automatique de reference avant de bloquer.',
      actions: [
        {
          kind: 'connector',
          connector: 'aurora_image',
          action: 'generate',
          params: {
            prompt: buildCreativeConnectorPrompt(ctx, intent, true),
            no_research: true,
            style: 'cinematic',
          },
        },
      ],
      expectedOutcome: 'Deuxieme tentative image simplifiee pour livrer un artefact au lieu de s arreter au premier echec.',
    }
  }
  if (failures.length >= 2) {
    const detail = failures.map((entry) => entry.result.error || entry.result.output || 'erreur inconnue').join('\n- ')
    return {
      reasoning: 'Deux tentatives de generation ont echoue. Je finalise avec un diagnostic concret au lieu de boucler silencieusement.',
      actions: [
        {
          kind: 'reply',
          message: [
            '## Generation bloquee apres recuperation',
            '',
            `J ai tente le module ${intent.connector}.${intent.action}, puis une alternative quand c etait possible.`,
            '',
            '## Erreurs observees',
            `- ${detail}`,
            '',
            '## Suite utile',
            '- Le fil Cowork garde la demande et les tentatives.',
            '- Relancer apres redemarrage du bridge/ComfyUI ou avec un prompt plus simple reprendra depuis ce contexte.',
          ].join('\n'),
        },
        { kind: 'finish', summary: 'Generation bloquee apres tentatives alternatives.' },
      ],
      expectedOutcome: 'L utilisateur recoit un diagnostic exploitable et pas une question generique.',
    }
  }

  if (intent.needsReferenceSearch && !hasCreativeReferenceSearch(ctx)) {
    return {
      reasoning: 'La demande melange des references connues et de la creation. Je collecte d abord du contexte visuel fiable, puis je genererai avec le module adapte.',
      actions: [
        {
          kind: 'think',
          topic: 'references creatives',
          thought: 'Je traite les noms propres comme des contraintes de fidelite visuelle. Je cherche des references, puis je produis l artefact avec le module local au lieu de demander au user de preciser.',
        },
        {
          kind: 'web_search',
          query: buildCreativeReferenceQuery(intent.prompt),
          limit: 6,
        },
      ],
      expectedOutcome: 'References contextuelles disponibles pour guider la generation locale.',
    }
  }

  if (intent.needsReferenceSearch && hasCreativeReferenceSearch(ctx) && !hasCreativeReferenceFetch(ctx)) {
    const urls = pickCreativeReferenceFetchUrls(ctx)
    if (urls.length > 0) {
      return {
        reasoning: 'La recherche a trouve des references. Je lis maintenant des sources utiles pour construire un vrai pack de contraintes avant de generer.',
        actions: [
          {
            kind: 'think',
            topic: 'pack references creatives',
            thought: 'Je transforme la recherche en ressources exploitables: sources, indices visuels, contraintes de reproduction, limites de style et elements a ne pas inventer.',
          },
          ...urls.map((url): CoworkAction => ({ kind: 'fetch', url })),
        ],
        expectedOutcome: 'Pages de reference recuperees pour nourrir le prompt de generation au lieu de lancer une sortie pauvre.',
      }
    }
  }

  if (!hasTriggeredCreativeConnector(ctx, intent)) {
    const params: Record<string, unknown> = {
      prompt: buildCreativeConnectorPrompt(ctx, intent),
    }
    if (intent.language) params.language = intent.language
    const active = getActiveProjectArtifact(ctx)
    if (intent.kind === 'model3d' && active?.kind === 'image' && (active.path || active.url || active.previewUrl)) {
      params.image_path = active.path || active.url || active.previewUrl
      params.images = [active.path || active.url || active.previewUrl]
    }
    if (intent.kind === 'game' && active && (active.path || active.url || active.previewUrl)) {
      params.model_path = active.kind === 'model3d' ? active.path || active.url || active.previewUrl : undefined
      params.image_path = active.kind === 'image' ? active.path || active.url || active.previewUrl : undefined
    }
    return {
      reasoning: `La demande demande une production ${creativeKindLabel(intent.kind)}. Je delegue au module interne ${intent.connector} au lieu de repondre par une clarification.`,
      actions: [
        {
          kind: 'think',
          topic: 'production creative cowork',
          thought: `Hypothese par defaut: produire maintenant ${creativeKindLabel(intent.kind)} avec les references/contexte disponibles, puis verifier le resultat avant synthese.`,
        },
        {
          kind: 'connector',
          connector: intent.connector,
          action: intent.action,
          params,
        },
      ],
      expectedOutcome: `Le module ${intent.connector} produit un artefact exploitable, suivi par une verification/synthese au tour suivant.`,
    }
  }

  return null
}

function classifyCreativeProductionIntent(ctx: PlannerContext): CreativeProductionIntent | null {
  const raw = getEffectiveUserPrompt(ctx).trim()
  const text = normalizeIntentText(raw)
  const wantsCreate = /\b(cree|creer|crée|creer|genere|generer|génere|generes|fais|faire|fait|produis|produire|dessine|dessiner|compose|composer|concois|concevoir|transforme|convertis|modelise|modeliser|developpe|developper|anime|animer|ecris|ecrire)\b/.test(text)
  const hasActive = Boolean(getActiveProjectArtifact(ctx))
  if (!wantsCreate && !hasActive) return null

  const wantsGame = /\b(jeu|game|gameplay|jouable|personnage principal|boss|niveau|plateformer|platformer|fps|rpg|arcade)\b/.test(text)
  if (wantsGame) {
    return {
      kind: 'game',
      connector: 'aurora_code',
      action: 'generate',
      prompt: raw,
      needsReferenceSearch: wantsKnownReference(text),
      language: 'typescript',
    }
  }

  const wants3d = /\b(3d|modele 3d|model 3d|mesh|glb|gltf|objet 3d|asset 3d|figurine|avatar 3d|modelise|modeliser)\b/.test(text)
  if (wants3d) {
    return {
      kind: 'model3d',
      connector: 'aurora_3d',
      action: 'generate',
      prompt: raw,
      needsReferenceSearch: wantsKnownReference(text),
    }
  }

  const wantsVideo = /\b(video|clip|film|animation|anime ce|anime le|compose une video|rendu video)\b/.test(text)
  if (wantsVideo) {
    return {
      kind: 'video',
      connector: 'aurora_video',
      action: 'generate',
      prompt: raw,
      needsReferenceSearch: wantsKnownReference(text),
    }
  }

  const wantsAudio = /\b(voix|audio|tts|lis a voix haute|parle|voix off|narration)\b/.test(text)
  if (wantsAudio) {
    return {
      kind: 'audio',
      connector: 'aurora_voice',
      action: 'speak',
      prompt: raw,
      needsReferenceSearch: false,
    }
  }

  const wantsImage = /\b(image|photo|visuel|illustration|portrait|affiche|logo|rendu|fond|decor|décor|scene|scène|wallpaper|avatar|hero shot)\b/.test(text)
  if (wantsImage) {
    return {
      kind: 'image',
      connector: 'aurora_image',
      action: 'generate',
      prompt: raw,
      needsReferenceSearch: wantsKnownReference(text),
    }
  }

  const wantsCode = /\b(code|script|page|site|app|application|composant|html|css|javascript|typescript|python|react|vite)\b/.test(text)
  if (wantsCode) {
    return {
      kind: 'code',
      connector: 'aurora_code',
      action: 'generate',
      prompt: raw,
      needsReferenceSearch: false,
      language: inferRequestedLanguage(text),
    }
  }

  return null
}

function wantsKnownReference(text: string): boolean {
  return /\b(reference|fidele|ressembl|reprodu|celebrite|celebrity|personne reelle|personnage connu|marque|logo officiel|emmanuel macron|macron|president|presidentiel|kirua|killua|hunter x hunter|anime connu|manga connu)\b/.test(text)
}

function hasCreativeReferenceSearch(ctx: PlannerContext): boolean {
  return ctx.history.some((entry) =>
    entry.action.kind === 'web_search'
    && /reference|visuel|portrait|image|design|official|officiel|style/i.test(entry.action.query),
  )
}

function hasCreativeReferenceFetch(ctx: PlannerContext): boolean {
  return ctx.history.some((entry) => entry.action.kind === 'fetch' && entry.result.ok)
}

function pickCreativeReferenceFetchUrls(ctx: PlannerContext): string[] {
  const urls: string[] = []
  const seen = new Set<string>()
  for (const entry of ctx.history) {
    if (entry.action.kind !== 'web_search' || !entry.result.ok) continue
    for (const url of extractReferenceUrlsFromSearchEntry(entry)) {
      if (seen.has(url) || !isUsefulCreativeReferenceUrl(url)) continue
      seen.add(url)
      urls.push(url)
      if (urls.length >= 3) return urls
    }
  }
  return urls
}

function extractReferenceUrlsFromSearchEntry(entry: PlannerContext['history'][number]): string[] {
  const urls: string[] = []
  const data = entry.result.data
  if (data && typeof data === 'object' && Array.isArray((data as { hits?: unknown }).hits)) {
    for (const hit of (data as { hits: Array<{ url?: unknown }> }).hits) {
      if (typeof hit?.url === 'string') urls.push(cleanupReferenceUrl(hit.url))
    }
  }
  for (const match of (entry.result.output || '').matchAll(/https?:\/\/[^\s"'<>]+/gi)) {
    urls.push(cleanupReferenceUrl(match[0]))
  }
  return urls.filter(Boolean)
}

function cleanupReferenceUrl(url: string): string {
  return url.replace(/[),.;\]}]+$/g, '')
}

function isUsefulCreativeReferenceUrl(url: string): boolean {
  if (!/^https?:\/\//i.test(url)) return false
  if (/\.(png|jpe?g|gif|webp|svg|mp4|webm|zip|pdf)(?:[?#].*)?$/i.test(url)) return false
  if (/\/search[/?]|duckduckgo\.com|google\./i.test(url)) return false
  return true
}

function hasTriggeredCreativeConnector(ctx: PlannerContext, intent: CreativeProductionIntent): boolean {
  return ctx.history.some((entry) =>
    entry.action.kind === 'connector'
    && entry.action.connector === intent.connector
    && entry.action.action === intent.action,
  )
}

function findLatestCreativeConnectorEntry(
  ctx: PlannerContext,
  intent: CreativeProductionIntent,
): PlannerContext['history'][number] | null {
  for (let i = ctx.history.length - 1; i >= 0; i -= 1) {
    const entry = ctx.history[i]
    if (
      entry.action.kind === 'connector'
      && entry.action.connector === intent.connector
      && entry.action.action === intent.action
    ) {
      return entry
    }
  }
  return null
}

function findCreativeConnectorFailures(
  ctx: PlannerContext,
  intent: CreativeProductionIntent,
): PlannerContext['history'] {
  return ctx.history.filter((entry) =>
    entry.action.kind === 'connector'
    && entry.action.connector === intent.connector
    && entry.action.action === intent.action
    && !entry.result.ok,
  )
}

function buildCreativeReferenceQuery(prompt: string): string {
  return [
    'references visuelles fiables',
    prompt.replace(/\s+/g, ' ').slice(0, 180),
    'portrait design decor style officiel',
  ].join(' ')
}

function buildCreativeConnectorPrompt(
  ctx: PlannerContext,
  intent: CreativeProductionIntent,
  simplified = false,
): string {
  const active = getActiveProjectArtifact(ctx)
  const referenceContext = summarizeCreativeReferenceHistory(ctx.history)
  const wantsAppLike = /\b(app|application|site|jeu|game|jouable|lancable|lançable|emulateur|prototype)\b/i.test(intent.prompt)
  const wantsBranding = /\b(logo|marque|brand|identite|identité|palette|ui|interface|hud)\b/i.test(intent.prompt) || wantsAppLike
  const lines = [
    '# Brief Cowork - production creative multi-passes',
    '',
    `Objectif client: ${intent.prompt}`,
    'Traite la demande comme un brief client reel: ne refuse pas par manque de precision, choisis une hypothese professionnelle et produis un resultat fini.',
    '',
    '## Contraintes non negociables',
    '- Respecte le dernier message utilisateur et le fil projet actif; les mots "celle-ci", "celui-ci", "ce modele", "la version modifiee" pointent vers la reference active.',
    '- Separe reference connue et creation originale: reproduis les traits/indices utiles quand la reference est fournie, mais signale clairement ce qui est interprete ou stylise.',
    '- Ne livre pas un artefact isole si la demande implique une chaine: produis les ressources intermediaires utiles et relie-les dans la sortie.',
    '- Si une generation echoue, degrade intelligemment: version simplifiee, asset procedurale, ou code local testable, mais pas abandon generique.',
    '',
    '## Passes requises',
    '1. Comprendre le brief client et extraire les entites, references, contraintes et inconnues.',
    '2. Construire un pack de ressources: references, palette, formes/silhouette, logo/branding si utile, assets manquants, dependances entre versions.',
    '3. Produire l artefact principal avec chemins ou URLs exploitables par Cowork.',
    '4. Verifier: rendu ouvrable, dimensions/format, coherence avec le brief, dependances image->3D->jeu ou image->code respectees.',
    '5. Si la verification echoue, corriger et relancer une passe avant de finaliser.',
  ]
  if (intent.kind === 'image') {
    lines.push(
      '',
      '## Livrable image',
      '- Image finale soignee, composition lisible, sujet principal identifiable, fond integre, style coherent.',
      '- Inclure un court manifest: sujet, fond, style, references utilisees, version, chemin/preview.',
      '- Si le user demande une modification, creer une nouvelle version et la marquer comme reference active.',
    )
  } else if (intent.kind === 'model3d') {
    lines.push(
      '',
      '## Livrable 3D',
      '- Modele 3D exploitable, silhouette fidele, materiaux propres, reference active respectee si fournie.',
      '- Fournir chemin GLB/GLTF/OBJ, preview si disponible, contraintes de scale/origine, et lien parent vers image/source.',
      '- Si la reference est une image, conserver couleurs dominantes, silhouette, accessoires et intention de pose.',
    )
  } else if (intent.kind === 'game') {
    lines.push(
      '',
      '## Livrable jeu/app',
      '- Jeu ou app jouable complet: pas seulement un personnage. Inclure boucle de gameplay, objectifs, controles, camera/vue, collisions ou scoring, et feedback visuel.',
      '- Creer les ressources manquantes si necessaire: logo, palette, HUD, sprite/mesh fallback, fond, icones, ecran titre, instructions.',
      '- L artefact doit etre lancable dans l emulateur Cowork ou via commande locale. Retourner index.html ou projet avec commande de lancement.',
      '- Inclure une verification concrete: build/test, smoke test, capture/preview, ou explication precise si un module externe est indisponible.',
    )
  } else if (intent.kind === 'code') {
    lines.push(
      '',
      '## Livrable code/app',
      '- Code complet, executable et structure, avec commentaires utiles uniquement quand necessaire.',
      '- Si le brief parle d app, logo, UI ou demo: livrer une app lancable avec branding, assets, et etat interactif; pas un snippet.',
      '- Inclure commandes de lancement/test, fichiers principaux, et fallback si une dependance ou un outil est absent.',
    )
  } else if (intent.kind === 'video') {
    lines.push(
      '',
      '## Livrable video',
      '- Courte video composee avec rythme, scenes, transitions et coherence visuelle.',
      '- Inclure storyboard, ressources utilisees, duree, format de sortie et verification de lecture.',
    )
  }
  if (active) {
    lines.push(
      '',
      '## Reference active Cowork',
      `${active.label} (${active.kind}) path=${active.path || active.url || active.previewUrl || 'non expose'}.`,
    )
  }
  if (referenceContext) {
    lines.push(
      '',
      '## Contexte de recherche/reference deja collecte',
      referenceContext,
      '',
      'Utilise ces sources comme pack de reconnaissance: extrais les traits utiles, les contraintes de decor/style, les details a eviter, et les zones ou il faut styliser au lieu d inventer.',
    )
  }
  if (wantsBranding) {
    lines.push(
      '',
      '## Branding et ressources attendues',
      '- Produire ou decrire un logo coherent avec le projet, pas un texte brut.',
      '- Definir palette, typographie/systeme UI, icones/HUD et tonalite visuelle.',
      '- Chaque ressource doit avoir un nom stable, un role, et un chemin/URL/data URI si elle est generable dans ce passage.',
    )
  }
  if (wantsAppLike) {
    lines.push(
      '',
      '## Contrat app lancable',
      '- Le rendu doit etre ouvrable sans etapes cachees: index.html autonome ou projet avec commande claire.',
      '- Prevoir un mode preview/emulateur Cowork: canvas/iframe fonctionnel, pas d ecran vide, pas de dependance introuvable.',
      '- Tester un chemin utilisateur minimal: charger, voir le logo/ecran titre, interagir, obtenir un feedback.',
    )
  }
  if (simplified) {
    lines.push(
      '',
      '## Mode recuperation',
      'Simplifie la composition, evite les dependances de reference fragiles, conserve les elements essentiels, et livre une version utile plutot que de bloquer.',
    )
  }
  lines.push(
    '',
    '## Format de sortie attendu',
    '- Reponds avec les chemins/URLs de chaque artefact et un court manifest de ressources.',
    '- Mentionne quelle version devient active pour la suite.',
    '- Mentionne les verifications effectuees ou les raisons techniques precises si une verification ne peut pas tourner.',
  )
  return lines.join('\n')
}

function summarizeCreativeReferenceHistory(history: PlannerContext['history']): string {
  return history
    .filter((entry) => entry.action.kind === 'web_search' || entry.action.kind === 'fetch')
    .slice(-4)
    .map((entry) => {
      const label = entry.action.kind === 'web_search' ? `web_search ${entry.action.query}` : `fetch ${entry.action.url}`
      const output = (entry.result.output || entry.result.error || '').replace(/\s+/g, ' ').trim().slice(0, 500)
      return `- ${label}: ${output || (entry.result.ok ? 'OK' : 'KO')}`
    })
    .join('\n')
}

function getActiveProjectArtifact(ctx: PlannerContext) {
  const thread = ctx.projectThread
  if (!thread?.artifacts?.length) return null
  if (thread.activeArtifactId) {
    const active = thread.artifacts.find((artifact) => artifact.id === thread.activeArtifactId)
    if (active) return active
  }
  const ready = thread.artifacts.filter((artifact) => artifact.status === 'ready')
  return ready[ready.length - 1] ?? thread.artifacts[thread.artifacts.length - 1] ?? null
}

function buildCreativeProductionReply(
  ctx: PlannerContext,
  intent: CreativeProductionIntent,
  entry: PlannerContext['history'][number],
): string {
  const path = extractCreativeOutputPath(entry.result.data) || extractFirstArtifactPath(entry.result.output || '')
  const output = (entry.result.output || '').trim()
  const active = getActiveProjectArtifact(ctx)
  return [
    '## Creation terminee',
    '',
    `- Type : **${creativeKindLabel(intent.kind)}**`,
    `- Module utilise : \`${intent.connector}.${intent.action}\``,
    path ? `- Sortie : \`${path}\`` : '- Sortie : ajoutee au fil Cowork.',
    active ? `- Reference precedente prise en compte : ${active.label}` : '',
    '',
    '## Dans la conversation',
    '- L apercu, le telechargement et les actions de visualisation sont disponibles sur la carte de l artefact.',
    intent.kind === 'code' || intent.kind === 'game'
      ? '- Pour le code/jeu : bascule entre **Code** colore et **Emulateur** directement dans la bulle.'
      : '',
    output && !path ? `\n## Resultat brut\n${output.slice(0, 1200)}` : '',
  ].filter(Boolean).join('\n')
}

function extractCreativeOutputPath(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  const direct = data as Record<string, unknown>
  for (const key of ['path', 'outputPath', 'audio_url', 'url']) {
    const value = direct[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  const serialized = JSON.stringify(data)
  return extractFirstArtifactPath(serialized)
}

function extractFirstArtifactPath(text: string): string | null {
  const match = text.match(/(?:[A-Za-z]:[\\/][^\s"'<>]+|\/[^\s"'<>]+|(?:\.\/)?(?:output|public|dist|src|app|application)[\\/][^\s"'<>]+)\.(?:png|jpe?g|webp|gif|glb|gltf|obj|fbx|mp4|webm|html|css|jsx?|tsx?|py|rs|go|json|wav|mp3|zip)/i)
  return match ? match[0].replace(/[),.;\]}]+$/g, '') : null
}

function creativeKindLabel(kind: CreativeProductionKind): string {
  switch (kind) {
    case 'image': return 'image'
    case 'model3d': return 'modele 3D'
    case 'game': return 'jeu'
    case 'code': return 'code'
    case 'video': return 'video'
    case 'audio': return 'audio'
  }
}

function inferRequestedLanguage(text: string): string | undefined {
  if (/\btypescript|tsx|react\b/.test(text)) return 'typescript'
  if (/\bjavascript|js|canvas\b/.test(text)) return 'javascript'
  if (/\bpython|py\b/.test(text)) return 'python'
  if (/\bhtml|css|site|page\b/.test(text)) return 'html'
  if (/\brust\b/.test(text)) return 'rust'
  return undefined
}

function buildAcademicWebResearchPlan(ctx: PlannerContext): CoworkPlan | null {
  if (!isPublicAcademicWebResearchRequest(ctx)) return null
  const searchEntries = ctx.history.filter((entry) => entry.action.kind === 'web_search')
  if (searchEntries.length === 0) {
    return {
      reasoning: 'La demande vise des sujets/fichiers publics en ligne. Je lance une recherche web native, sans Aurora-Connect.',
      actions: [
        {
          kind: 'think',
          topic: 'recherche academique publique',
          thought: 'Recherche publique : utiliser web_search puis fetch sur les resultats utiles. Aurora-Connect n est pas requis car je ne manipule pas un onglet utilisateur.',
        },
        {
          kind: 'web_search',
          query: buildAcademicWebSearchQuery(getAcademicResearchIntentText(ctx)),
          limit: 6,
        },
      ],
      expectedOutcome: 'Resultats web publics disponibles pour selectionner les sources et sujets utiles.',
    }
  }

  const urls = extractUsefulAcademicUrls(ctx.history)
  const fetched = new Set(ctx.history
    .filter((entry) => entry.action.kind === 'fetch')
    .map((entry) => entry.action.kind === 'fetch' ? entry.action.url : '')
    .filter(Boolean))
  const nextUrls = urls.filter((url) => !fetched.has(url)).slice(0, 3)
  if (nextUrls.length > 0) {
    return {
      reasoning: 'La recherche native a trouve des sources potentielles. Je lis les pages/fichiers utiles avec fetch avant de produire la fiche.',
      actions: nextUrls.map((url) => ({ kind: 'fetch' as const, url })),
      expectedOutcome: 'Sources web lues pour permettre une synthese fiable et citee.',
    }
  }

  const failedSearches = searchEntries.filter((entry) => !entry.result.ok).length
  const emptySearches = searchEntries.filter((entry) => entry.result.ok && extractWebSearchHitCount(entry) === 0).length
  if ((failedSearches > 0 || emptySearches > 0 || urls.length === 0) && searchEntries.length < 4) {
    const query = buildAcademicRetrySearchQuery(ctx, searchEntries.length)
    return {
      reasoning: 'La premiere recherche native a echoue ou n a rien donne. Je tente une requete plus ciblee avant de conclure.',
      actions: [
        {
          kind: 'web_search',
          query,
          limit: 6,
        },
      ],
      expectedOutcome: 'Deuxieme recherche officielle pour eviter de bloquer sur le premier essai.',
    }
  }

  const academicArtifact = buildAcademicPdfDescriptor(ctx)
  if (academicArtifact && shouldProduceAcademicPdf(ctx)) {
    const verified = findLatestSuccessfulRead(ctx.history, academicArtifact.path)
    const written = findLatestActionForPath(ctx.history, 'write_file', academicArtifact.path)
    const fallbackVerified = findLatestSuccessfulRead(ctx.history, academicArtifact.fallbackPath)
    const fallbackWritten = findLatestActionForPath(ctx.history, 'write_file', academicArtifact.fallbackPath)
    const completedPath = written?.result.ok && verified?.result.ok
      ? academicArtifact.path
      : (fallbackWritten?.result.ok && fallbackVerified?.result.ok ? academicArtifact.fallbackPath : null)
    if (completedPath) {
      return {
        reasoning: 'La recherche officielle a ete tentee, le PDF a ete ecrit puis relu. Je finalise avec le chemin verifie et les sources.',
        actions: [
          {
            kind: 'reply',
            message: buildAcademicPdfFinalReply(ctx, completedPath),
          },
          { kind: 'finish', summary: 'Fiche BAC STI2D SIN creee et verifiee.' },
        ],
        expectedOutcome: 'L utilisateur recoit le chemin du PDF verifie et un resume des sources consultees.',
      }
    }
    const outputPath = written && !written.result.ok ? academicArtifact.fallbackPath : academicArtifact.path
    const pdf = buildAcademicRevisionPdf(ctx, outputPath)
    return {
      reasoning: 'Les recherches/fetchs disponibles ont ete exploites. Je cree maintenant le PDF de revision puis je le relis avant de finaliser.',
      actions: [
        { kind: 'write_file', path: outputPath, content: pdf },
        { kind: 'read_file', path: outputPath },
      ],
      expectedOutcome: 'Fiche PDF creee localement et verification de lecture effectuee.',
    }
  }

  return null
}

function isPublicAcademicWebResearchRequest(ctx: PlannerContext): boolean {
  const current = normalizeIntentText(getAcademicResearchIntentText(ctx))
  const wantsAcademic = /\b(bac|sti2d|sin|tp|controle|revision|reviser|competences?|schema|sujets?|annales?|banque|fichiers?|programme|officiel)\b/.test(current)
  const wantsOnline = /\b(recherch|internet|web|en ligne|site|telecharg|trouve|trouver|vrai|vrais|public|officiel|banque)\b/.test(current)
  const asksForBrowserTab = /\b(onglet|page ouverte|navigateur ouvert|clique|remplis|connecte toi|connecte-toi)\b/.test(current)
  return wantsAcademic && wantsOnline && !asksForBrowserTab
}

function shouldProduceAcademicPdf(ctx: PlannerContext): boolean {
  const intent = normalizeIntentText(getAcademicResearchIntentText(ctx))
  const wantsPdf = /\b(pdf|fiche|revision|reviser|controle|schema|competences?)\b/.test(intent)
  const hasFetch = ctx.history.some((entry) => entry.action.kind === 'fetch')
  const searches = ctx.history.filter((entry) => entry.action.kind === 'web_search')
  return wantsPdf && (hasFetch || searches.length >= 4)
}

function buildAcademicPdfDescriptor(ctx: PlannerContext): { path: string; fallbackPath: string } | null {
  const profile = inferUserProfilePath(ctx.workspaceRoot)
  const targetDir = profile ? joinWorkspacePath(profile, 'Desktop') : joinWorkspacePath(ctx.workspaceRoot || '.', 'output')
  return {
    path: joinWorkspacePath(targetDir, 'fiche_revision_bac_sti2d_sin_banque_fichiers_tp.pdf'),
    fallbackPath: joinWorkspacePath(targetDir, 'fiche_revision_sti2d_sin_tp.pdf'),
  }
}

function buildAcademicPdfFinalReply(ctx: PlannerContext, path: string): string {
  const sources = summarizeAcademicSources(ctx)
  return [
    'C est fait : j ai cherche des ressources officielles ou publiques, lu les sources accessibles, cree le PDF et verifie qu il est lisible.',
    '',
    `Fichier : \`${path}\``,
    '',
    'Le PDF contient une fiche de revision BAC STI2D specialite SIN orientee TP : schema de methode, competences a maitriser, notions cles, grille de verification et auto-test.',
    sources.length > 0 ? `\nSources/URLs prises en compte :\n${sources.map((source) => `- ${source}`).join('\n')}` : '',
  ].filter(Boolean).join('\n')
}

function buildAcademicRevisionPdf(ctx: PlannerContext, outputPath: string): string {
  return buildSimplePdf(buildAcademicRevisionLines(ctx, outputPath))
}

function buildAcademicRevisionLines(ctx: PlannerContext, outputPath: string): string[] {
  const intent = getAcademicResearchIntentText(ctx).replace(/\s+/g, ' ').trim()
  const sources = summarizeAcademicSources(ctx)
  const fetched = ctx.history.filter((entry) => entry.action.kind === 'fetch' && entry.result.ok)
  const searchCount = ctx.history.filter((entry) => entry.action.kind === 'web_search').length
  const officialSources = sources.filter((source) => /education\.gouv\.fr|eduscol|ac-[a-z-]+\.fr/i.test(source))
  const lines = [
    'Fiche de revision - BAC STI2D specialite SIN',
    'Sujet : banque des fichiers / fichiers officiels de TP',
    `Fichier verifie attendu : ${outputPath}`,
    '',
    'Mission utilisateur',
    intent || 'Creer une fiche de revision PDF a partir de recherches en ligne sur les fichiers officiels de TP.',
    '',
    'Sources recherchees et lues',
    `- Recherches web effectuees : ${searchCount}.`,
    `- Pages ou fichiers lus avec fetch : ${fetched.length}.`,
    officialSources.length > 0
      ? `- Sources officielles detectees : ${officialSources.slice(0, 6).join(' | ')}.`
      : '- Aucune source officielle parfaitement exploitable n a ete confirmee par fetch; la fiche garde donc une partie methode generale a verifier avec ton enonce officiel.',
    ...sources.slice(0, 10).map((source) => `- ${source}`),
    '',
    'Objectif pour le controle / TP',
    '- Comprendre le probleme technique avant de coder ou mesurer.',
    '- Identifier la chaine d information : acquerir, traiter, communiquer.',
    '- Relier chaque fichier fourni a son role : enonce, ressources, programme, donnees, schema, document reponse.',
    '- Justifier les choix avec des mesures, des tests ou des observations.',
    '- Produire une reponse claire : methode, resultats, interpretation, conclusion.',
    '',
    'Schema de methode pour un TP SIN',
    '1. Lire le cahier des charges et entourer les contraintes mesurables.',
    '2. Reperer les entrees/sorties : capteurs, actionneurs, interface, reseau, stockage.',
    '3. Faire le schema fonctionnel : utilisateur -> acquisition -> traitement -> communication -> action/affichage.',
    '4. Identifier les fichiers : code source, bibliotheques, donnees, captures, documents techniques.',
    '5. Tester par petites etapes : un capteur, une fonction, une trame, une requete, puis le systeme complet.',
    '6. Comparer le resultat obtenu avec le resultat attendu.',
    '7. Conclure en expliquant la cause des ecarts et les ameliorations possibles.',
    '',
    'Competences a maitriser',
    '- Lire et exploiter un document technique officiel.',
    '- Decrire une architecture de systeme numerique.',
    '- Analyser un algorithme ou un programme simple.',
    '- Modifier un code sans casser le comportement attendu.',
    '- Comprendre une trame, un protocole ou un echange de donnees.',
    '- Exploiter des mesures et captures pour valider une hypothese.',
    '- Presenter une demarche d ingenierie : probleme, solution, test, validation.',
    '',
    'Notions SIN a reviser',
    '- Chaine d information : acquisition, traitement, communication.',
    '- Capteurs/actionneurs : grandeur mesuree, signal, conversion, precision.',
    '- Programmation : variables, conditions, boucles, fonctions, tableaux, erreurs.',
    '- Reseaux/protocoles : adresse, client/serveur, requete, reponse, trame, debit.',
    '- Donnees/fichiers : format, lecture/ecriture, encodage, organisation, securite.',
    '- IHM : affichage, boutons, retour utilisateur, ergonomie.',
    '',
    'Carte mentale texte',
    '- TP officiel SIN',
    '  - Besoin : que doit faire le systeme ?',
    '  - Fichiers : enonce, ressources, code, donnees, document reponse.',
    '  - Analyse : schema fonctionnel, flux d information, contraintes.',
    '  - Realisation : modifier, parametrer, assembler, tester.',
    '  - Validation : mesures, captures, comparaison attendu/obtenu.',
    '  - Conclusion : expliquer pourquoi la solution marche ou non.',
    '',
    'Methode de reponse rapide',
    '- Commencer par une phrase de contexte : "Le systeme doit..."',
    '- Nommer les blocs : capteur, microcontroleur/carte, logiciel, reseau, interface.',
    '- Pour un code : expliquer l entree, le traitement, la sortie.',
    '- Pour un fichier : dire son role exact et comment il est exploite.',
    '- Pour une erreur : citer le symptome, la cause probable, le test de verification.',
    '',
    'Auto-test',
    '1. Peux-tu dessiner la chaine d information d un systeme SIN ?',
    '2. Peux-tu expliquer le role de chaque fichier donne dans un TP ?',
    '3. Sais-tu lire une trame ou une requete et identifier les donnees utiles ?',
    '4. Sais-tu modifier un programme puis prouver que le resultat fonctionne ?',
    '5. Sais-tu conclure avec une justification technique, pas seulement "ca marche" ?',
  ]
  const fetchedSnippets = fetched
    .map((entry) => {
      if (entry.action.kind !== 'fetch') return ''
      const snippet = (entry.result.output || '').replace(/\s+/g, ' ').trim().slice(0, 360)
      return snippet ? `Extrait source - ${entry.action.url}: ${snippet}` : ''
    })
    .filter(Boolean)
    .slice(0, 4)
  if (fetchedSnippets.length > 0) {
    lines.push('', 'Extraits utiles observes', ...fetchedSnippets)
  }
  return lines
}

function summarizeAcademicSources(ctx: PlannerContext): string[] {
  const sources: string[] = []
  for (const entry of ctx.history) {
    if (entry.action.kind === 'web_search') {
      const data = entry.result.data
      if (data && typeof data === 'object' && Array.isArray((data as { hits?: unknown }).hits)) {
        for (const hit of (data as { hits: unknown[] }).hits) {
          if (!hit || typeof hit !== 'object') continue
          const url = (hit as { url?: unknown }).url
          const title = (hit as { title?: unknown }).title
          if (typeof url === 'string' && url) {
            sources.push(`${typeof title === 'string' && title ? title + ' - ' : ''}${url}`)
          }
        }
      }
    }
    if (entry.action.kind === 'fetch') {
      sources.push(entry.action.url)
    }
  }
  return uniqueStrings(sources).slice(0, 12)
}

function getAcademicResearchIntentText(ctx: PlannerContext): string {
  const effectivePrompt = getEffectiveUserPrompt(ctx)
  const recentUserTurns = (ctx.conversationHistory ?? [])
    .filter((turn) => turn.role === 'user')
    .slice(-4)
    .map((turn) => turn.content)
  return [...recentUserTurns, effectivePrompt].join('\n')
}

function getEffectiveUserPrompt(ctx: PlannerContext): string {
  const frame = resolveCoworkConversationFrame(ctx.userPrompt, ctx.conversationHistory)
  return frame.effectivePrompt || ctx.userPrompt
}

function buildAcademicWebSearchQuery(prompt: string): string {
  const current = normalizeIntentText(prompt)
  const parts = [prompt.trim()]
  if (/\bsti2d\b/.test(current)) parts.push('bac STI2D sujets officiels')
  if (/\bsin\b/.test(current)) parts.push('specialite SIN systemes information numerique')
  if (/\b(tp|competences?|schema)\b/.test(current)) parts.push('TP competences schema evaluation')
  if (/\b(banque|fichiers?|sujets?)\b/.test(current)) parts.push('banque nationale sujets annales fichiers publics')
  if (/\bofficiel|officiels|officielles|eduscol\b/.test(current)) parts.push('ressources officielles Eduscol ministere education')
  parts.push('(site:eduscol.education.fr OR site:education.gouv.fr OR site:ac-*.fr) filetype:pdf')
  return uniqueStrings(parts)
    .join(' ')
    .replace(/\s+/g, ' ')
    .slice(0, 240)
}

function buildAcademicRetrySearchQuery(ctx: PlannerContext, attemptIndex: number): string {
  const intent = normalizeIntentText(getAcademicResearchIntentText(ctx))
  const variants = [
    'site:eduscol.education.fr STI2D SIN TP ressources officielles filetype:pdf',
    'site:education.gouv.fr STI2D SIN bac sujets annales banque nationale sujets officiel filetype:pdf',
    'site:ac-*.fr STI2D SIN TP systemes information numerique ressources pedagogiques fichier pdf',
    'STI2D SIN TP competences schema fiche revision bac systemes information numerique ressources officielles pdf',
    'bac STI2D enseignement specifique SIN sujets TP fichiers publics annales competences',
  ]
  if (/\bbanque\b/.test(intent) && /\bfichiers?\b/.test(intent)) {
    variants.unshift('banque fichiers bac STI2D SIN TP sujets officiels ressources publiques pdf eduscol')
  }
  return uniqueStrings(variants)[attemptIndex % uniqueStrings(variants).length]
}

function extractWebSearchHitCount(entry: PlannerContext['history'][number]): number {
  const data = entry.result.data
  if (data && typeof data === 'object' && Array.isArray((data as { hits?: unknown }).hits)) {
    return (data as { hits: unknown[] }).hits.length
  }
  const output = entry.result.output || ''
  if (!output.trim()) return 0
  const numbered = output.match(/(^|\n)\s*\d+\./g)
  if (numbered) return numbered.length
  const urls = output.match(/https?:\/\//g)
  return urls?.length ?? 0
}

function extractUsefulAcademicUrls(history: PlannerContext['history']): string[] {
  const urls: string[] = []
  for (const entry of history) {
    if (entry.action.kind !== 'web_search' || !entry.result.ok) continue
    const data = entry.result.data
    if (data && typeof data === 'object' && Array.isArray((data as { hits?: unknown }).hits)) {
      for (const hit of (data as { hits: unknown[] }).hits) {
        if (hit && typeof hit === 'object') {
          const url = (hit as { url?: unknown }).url
          if (typeof url === 'string') urls.push(url)
        }
      }
    }
    const outputUrls = (entry.result.output || '').match(/https?:\/\/[^\s)>\]]+/gi) || []
    urls.push(...outputUrls)
  }
  const clean = uniqueStrings(urls.map((url) => url.replace(/[.,;]+$/g, '')))
  const official = clean.filter(isLikelyOfficialAcademicUrl)
  return (official.length > 0 ? official : clean).slice(0, 6)
}

function isLikelyOfficialAcademicUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase()
    return host.endsWith('education.gouv.fr')
      || host.endsWith('eduscol.education.fr')
      || host.endsWith('enseignementsup-recherche.gouv.fr')
      || host.includes('education')
      || host.includes('ac-')
  } catch {
    return false
  }
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const value of values) {
    const clean = value.trim()
    if (!clean || seen.has(clean)) continue
    seen.add(clean)
    out.push(clean)
  }
  return out
}

function buildDesktopInventoryShellAction(mode: 'standard' | 'utf8_retry' = 'standard'): CoworkAction {
  const script = [
    "try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); $OutputEncoding = [Console]::OutputEncoding } catch {}",
    "$ProgressPreference='SilentlyContinue'",
    "$ErrorActionPreference='SilentlyContinue'",
    "Write-Output '## SYSTEME'",
    "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime,FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Depth 4",
    "Write-Output '## MATERIEL'",
    "Get-CimInstance Win32_ComputerSystem | Select-Object Name,Manufacturer,Model,SystemType,TotalPhysicalMemory,NumberOfProcessors,NumberOfLogicalProcessors | ConvertTo-Json -Depth 4",
    "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Depth 4",
    "Write-Output '## GPU'",
    "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,VideoModeDescription | ConvertTo-Json -Depth 4",
    "Write-Output '## DISQUES'",
    "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,VolumeName,@{Name='SizeGB';Expression={[math]::Round($_.Size/1GB,1)}},@{Name='FreeGB';Expression={[math]::Round($_.FreeSpace/1GB,1)}} | ConvertTo-Json -Depth 4",
    "Write-Output '## APPLICATIONS_ACTIVES'",
    "Get-Process | Sort-Object CPU -Descending | Select-Object -First 30 ProcessName,Id,CPU,@{Name='MemoryMB';Expression={[math]::Round($_.WorkingSet64/1MB,1)}},MainWindowTitle | ConvertTo-Json -Depth 4",
    "Write-Output '## BUREAU_UTILISATEUR'",
    "Get-ChildItem (Join-Path $env:USERPROFILE 'Desktop') -Force | Select-Object -First 80 Name,Mode,Length,LastWriteTime | ConvertTo-Json -Depth 4",
    mode === 'utf8_retry' ? "Write-Output '## RECOVERY'; Write-Output 'utf8_retry=true'" : "Write-Output '## RECOVERY'; Write-Output 'utf8_retry=false'",
  ].join('; ')

  return {
    kind: 'shell',
    command: 'powershell',
    args: ['-NoProfile', '-NonInteractive', '-Command', script],
    timeoutMs: 45_000,
  }
}

function buildDesktopAnalysisReply(history: PlannerContext['history']): string | null {
  const shellEntry = [...history].reverse().find((entry) => (
    entry.action.kind === 'shell'
    && typeof entry.result.output === 'string'
    && entry.result.output.includes('## SYSTEME')
  ))
  if (!shellEntry || !shellEntry.result.output?.trim()) return null
  const screenshotEntry = [...history].reverse().find((entry) => entry.action.kind === 'screenshot_desktop')
  const screenshotData = screenshotEntry?.result.data as { path?: string; sizeKB?: number } | undefined
  const output = shellEntry.result.output
  const section = (name: string) => {
    const re = new RegExp(`## ${name}([\\s\\S]*?)(?=\\n## |$)`, 'i')
    const match = output.match(re)
    return (match?.[1] || '').trim()
  }
  const system = section('SYSTEME')
  const hardware = section('MATERIEL')
  const gpu = section('GPU')
  const disks = section('DISQUES')
  const apps = section('APPLICATIONS_ACTIVES')
  const desktop = section('BUREAU_UTILISATEUR')
  const block = (value: string, empty: string) => value
    ? `\`\`\`text\n${value.slice(0, 5000)}\n\`\`\``
    : empty

  return [
    '## FICHE RECAPITULATIVE — SYSTEME ET BUREAU',
    '',
    '### Systeme',
    block(system, 'Information systeme non disponible dans la collecte.'),
    '',
    '### Materiel',
    block(hardware, 'Information materiel non disponible dans la collecte.'),
    '',
    '### GPU et affichage',
    block(gpu, 'Information GPU non disponible dans la collecte.'),
    '',
    '### Stockage',
    block(disks, 'Information disque non disponible dans la collecte.'),
    '',
    '### Applications actives',
    block(apps, 'Liste des applications actives non disponible dans la collecte.'),
    '',
    '### Bureau utilisateur',
    block(desktop, 'Contenu du dossier Bureau non disponible dans la collecte.'),
    '',
    '### Capture ecran',
    screenshotData?.path
      ? `Capture conservee : \`${screenshotData.path}\`${screenshotData.sizeKB ? ` (${screenshotData.sizeKB} KB)` : ''}. Elle sert de contexte visuel, mais la fiche ci-dessus s'appuie surtout sur les donnees systeme textuelles.`
      : 'Aucune capture exploitable dans cette collecte, mais la fiche systeme reste produite avec les donnees disponibles.',
  ].join('\n')
}

function countDesktopInventoryShellFailures(history: PlannerContext['history']): number {
  return history.filter((entry) => (
    isDesktopInventoryShellAction(entry.action)
    && !entry.result.ok
  )).length
}

function isDesktopInventoryShellAction(action: CoworkAction): boolean {
  if (action.kind !== 'shell') return false
  if (!/powershell|pwsh/i.test(action.command)) return false
  const script = (action.args || []).join(' ')
  return script.includes('## SYSTEME') && script.includes('## APPLICATIONS_ACTIVES')
}

function buildDesktopPartialReply(history: PlannerContext['history']): string | null {
  const screenshotEntry = [...history].reverse().find((entry) => entry.action.kind === 'screenshot_desktop')
  const screenshotData = screenshotEntry?.result.data as { path?: string; sizeKB?: number } | undefined
  const failures = history
    .filter((entry) => isDesktopInventoryShellAction(entry.action) && !entry.result.ok)
    .map((entry) => entry.result.error || entry.result.output || 'Erreur inconnue')
  if (!screenshotEntry && failures.length === 0) return null

  return [
    '## FICHE RECAPITULATIVE — SYSTEME ET BUREAU',
    '',
    '### Etat de la collecte',
    '- Capture visuelle : ' + (screenshotData?.path
      ? `OK, conservee dans \`${screenshotData.path}\`${screenshotData.sizeKB ? ` (${screenshotData.sizeKB} KB)` : ''}.`
      : 'non disponible.'),
    `- Collecte systeme textuelle : ${failures.length > 0 ? 'KO apres recuperation automatique.' : 'non disponible.'}`,
    '',
    '### Ce qui est fiable maintenant',
    screenshotData?.path
      ? '- Une capture du bureau existe et peut etre analysee visuellement dans un passage suivant.'
      : '- Aucune donnee systeme exploitable n a ete retournee par le runtime actuel.',
    '- Aurora ne relance pas la meme commande en boucle : elle finalise avec le diagnostic technique utile.',
    '',
    '### Erreurs techniques',
    failures.length > 0
      ? failures.map((err, i) => `${i + 1}. ${err.slice(0, 700)}`).join('\n')
      : 'Aucune erreur shell detaillee dans l historique.',
    '',
    '### Conclusion',
    'La demande n est pas abandonnee : la collecte automatique a ete tentee, une recuperation UTF-8 a ete essayee, puis la fiche partielle est rendue avec les elements disponibles.',
  ].join('\n')
}

function isDesktopAnalysisRequest(ctx: PlannerContext): boolean {
  const normalize = (value: string) => value
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
  const current = normalize(getEffectiveUserPrompt(ctx))
  const history = normalize((ctx.conversationHistory || []).map((m) => m.content).join(' '))
  const wantsAnalysis = /\b(analyse|analyser|inspecte|resume|recap|fiche|decris|diagnostic)\b/.test(current)
  const targetsComputer = /\b(bureau|pc|ordinateur|machine|systeme|poste|desktop)\b/.test(current)
    || current.includes('espace informatique')
  if (wantsAnalysis && targetsComputer) return true
  return current.includes('espace informatique') && /\b(analyse|bureau|fiche|recap)\b/.test(history)
}

// ---------------------------------------------------------------------------
// Internal — chat + parse + retry
// ---------------------------------------------------------------------------

function buildWorkspaceInventoryShellAction(workspaceRoot: string): CoworkAction {
  return {
    kind: 'shell',
    command: 'rg',
    args: [
      '--files',
      '--hidden',
      '--glob', '!.git/**',
      '--glob', '!node_modules/**',
      '--glob', '!dist/**',
      '--glob', '!build/**',
      '--glob', '!target/**',
      '--glob', '!.venv/**',
      '--glob', '!__pycache__/**',
      '--glob', '!*.png',
      '--glob', '!*.jpg',
      '--glob', '!*.jpeg',
      '--glob', '!*.gif',
      '--glob', '!*.webp',
      '--glob', '!*.mp4',
      '--glob', '!*.glb',
      '--glob', '!*.dll',
      '--glob', '!*.zip',
      '--glob', '!*.7z',
    ],
    cwd: workspaceRoot || undefined,
    timeoutMs: 45_000,
  }
}

type UserFolderTarget = {
  id: 'desktop' | 'documents' | 'downloads'
  label: string
  path: string
}

type UserFolderFileFilter = {
  label: string
  extensions: string[]
}

function isUserFolderTargetRequest(ctx: PlannerContext): boolean {
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  return /\b(mon|ma|mes|le|la|les|dossier|fichiers?).{0,32}\b(bureau|desktop|documents?|telechargements?|downloads?)\b/.test(current)
    || /\b(bureau|desktop|documents?|telechargements?|downloads?)\b.{0,32}\b(dossier|fichiers?)\b/.test(current)
}

function isUserFolderOverviewRequest(ctx: PlannerContext): boolean {
  if (isDesktopAnalysisRequest(ctx)) return false
  if (!isUserFolderTargetRequest(ctx)) return false
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  if (hasExplicitArtifactOutputRequest(current)) return false
  const wantsOverview = /\b(topo|liste|lister|inventaire|recap|recapitulatif|resume|resumer|apercu|vue d ensemble|analyse|analyser|decris|decrire|quels?|quoi)\b/.test(current)
  const targetsContent = /\b(fichiers?|dossiers?|contenu|bureau|desktop|documents?|telechargements?|downloads?)\b/.test(current)
  return wantsOverview && targetsContent
}

function isUserFolderArtifactRequest(ctx: PlannerContext): boolean {
  if (isDesktopAnalysisRequest(ctx)) return false
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  const targetsUserFolder = isUserFolderTargetRequest(ctx)
  const wantsPdfArtifact = /\bpdf\b/.test(current)
  const hasSupportedDeterministicTopic = /\b(seconde|2e|deuxieme).{0,24}guerre.{0,24}mondiale\b/.test(current) || /\b(ww2|wwii)\b/.test(current)
  const wantsCreation = /\b(fais|fait|cree|creer|genere|generer|produis|produire|redige|rediger|ecris|ecrire|mets|mettre|prepare|preparer)\b/.test(current)
  const wantsScanThenCreate = /\b(scan|scanne|scanner|parcours|parcourir|lis|lire|regarde|analyse|analyser)\b/.test(current) && wantsPdfArtifact
  return targetsUserFolder && wantsPdfArtifact && hasSupportedDeterministicTopic && (wantsCreation || wantsScanThenCreate)
}

function buildUserFolderFilteredListingPlan(ctx: PlannerContext): CoworkPlan | null {
  if (isDesktopAnalysisRequest(ctx)) return null
  if (!isUserFolderTargetRequest(ctx)) return null
  const filter = resolveUserFolderFileFilter(ctx)
  if (!filter) return null
  const target = resolveUserFolderTarget(ctx)
  if (!target) return null

  const listing = findLatestListDirForPath(ctx.history, target.path)
  if (!listing) {
    return {
      reasoning: `La demande vise ${target.label} avec un filtre ${filter.label}. Je scanne directement le dossier utilisateur au lieu de demander un chemin deja inferable.`,
      actions: [
        {
          kind: 'think',
          topic: 'scan dossier utilisateur',
          thought: `Objectif courant : parcourir ${target.path} et ne ressortir que les fichiers ${filter.label}. Je n ai pas besoin de demander un chemin pour un dossier utilisateur standard.`,
        },
        { kind: 'list_dir', path: target.path, depth: 8 },
      ],
      expectedOutcome: `Aurora obtient la liste du dossier ${target.label} pour filtrer les fichiers ${filter.label}.`,
    }
  }

  return {
    reasoning: `Le dossier ${target.label} a ete scanne. Je filtre le resultat et je rends uniquement les fichiers ${filter.label}.`,
    actions: [
      { kind: 'reply', message: buildUserFolderFilteredListingReply(target, filter, listing.result.output || '') },
      { kind: 'finish', summary: `Liste ${filter.label} du dossier ${target.label} produite.` },
    ],
    expectedOutcome: `L utilisateur recoit uniquement les fichiers ${filter.label} trouves dans ${target.label}.`,
  }
}

function resolveUserFolderFileFilter(ctx: PlannerContext): UserFolderFileFilter | null {
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  if (hasExplicitArtifactOutputRequest(current)) return null
  const wantsScan = /\b(scan|scanne|scanner|parcours|parcourir|liste|lister|affiche|afficher|montre|montrer|trouve|trouver|cherche|chercher|ressors|ressort|sors|sort|donne|donner)\b/.test(current)
  const wantsOnly = /\b(que|uniquement|seulement|juste|filtre|filtrer|seuls?|seules?)\b/.test(current)
  if (!wantsScan && !wantsOnly) return null

  if (/\bpdfs?\b/.test(current)) return { label: 'PDF', extensions: ['.pdf'] }
  if (/\b(images?|photos?|captures?)\b/.test(current)) {
    return { label: 'images', extensions: ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.svg', '.ico'] }
  }
  if (/\b(videos?|films?|clips?)\b/.test(current)) {
    return { label: 'videos', extensions: ['.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'] }
  }
  if (/\b(audios?|sons?|musiques?)\b/.test(current)) {
    return { label: 'audios', extensions: ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.opus'] }
  }
  if (/\b(archives?|zip|rar|7z)\b/.test(current)) {
    return { label: 'archives', extensions: ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'] }
  }
  if (/\b(excel|xlsx?|csv|tableurs?|classeurs?)\b/.test(current)) {
    return { label: 'tableurs', extensions: ['.xlsx', '.xls', '.csv', '.ods'] }
  }
  if (/\b(word|docx?|odt)\b/.test(current)) {
    return { label: 'documents Word', extensions: ['.doc', '.docx', '.odt'] }
  }
  if (/\b(documents?|textes?|notes?)\b/.test(current)) {
    return { label: 'documents', extensions: ['.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.md'] }
  }
  if (/\b(code|scripts?)\b/.test(current)) {
    return { label: 'fichiers code', extensions: ['.ts', '.tsx', '.js', '.jsx', '.py', '.rs', '.html', '.css', '.json', '.md', '.sh', '.ps1', '.bat'] }
  }
  return null
}

function buildUserFolderFilteredListingReply(
  target: UserFolderTarget,
  filter: UserFolderFileFilter,
  output: string,
): string {
  const matches = parseUserFolderListing(output)
    .map((entry) => isAbsoluteWorkspacePath(entry) ? normalizeWorkspacePath(entry) : joinWorkspacePath(target.path, entry))
    .filter((path) => hasAnyExtension(path, filter.extensions))
    .filter(uniqueString)
    .sort((a, b) => a.localeCompare(b))
  const shown = matches.slice(0, 1000)
  const hidden = Math.max(0, matches.length - shown.length)

  return [
    `## Fichiers ${filter.label} dans ${target.label}`,
    '',
    `Chemin scanne : \`${target.path}\``,
    `Fichiers trouves : **${matches.length}**`,
    '',
    shown.length > 0
      ? shown.map((path) => `- \`${path}\``).join('\n')
      : `- Aucun fichier ${filter.label} detecte dans le scan.`,
    hidden > 0 ? `\n\n... ${hidden} autre(s) fichier(s) non affiche(s).` : '',
  ].filter(Boolean).join('\n')
}

function hasAnyExtension(path: string, extensions: string[]): boolean {
  const lower = normalizeWorkspacePath(path).toLowerCase()
  return extensions.some((extension) => lower.endsWith(extension))
}

function hasExplicitArtifactOutputRequest(current: string): boolean {
  return /\b(pdf|excel|xlsx|xls|csv|tableur|classeur|docx|word|document|fiche|rapport|expose|presentation|pptx|css|html|javascript|typescript|python|script|assembleur|assembly|asm|site|app|application|projet)\b/.test(current)
    && /\b(fais|fait|cree|creer|genere|generer|produis|produire|redige|rediger|ecris|ecrire|code|developpe|implemente|mets|mettre|prepare|preparer)\b/.test(current)
}

function resolveUserFolderTarget(ctx: PlannerContext): UserFolderTarget | null {
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  const profile = inferUserProfilePath(ctx.workspaceRoot)
  if (!profile) return null
  if (/\b(telechargements?|downloads?)\b/.test(current)) {
    return { id: 'downloads', label: 'Telechargements', path: joinWorkspacePath(profile, 'Downloads') }
  }
  if (/\bdocuments?\b/.test(current)) {
    return { id: 'documents', label: 'Documents', path: joinWorkspacePath(profile, 'Documents') }
  }
  if (/\b(bureau|desktop)\b/.test(current)) {
    return { id: 'desktop', label: 'Bureau', path: joinWorkspacePath(profile, 'Desktop') }
  }
  return null
}

function inferUserProfilePath(workspaceRoot: string): string | null {
  const normalized = normalizeWorkspacePath(workspaceRoot)
  const win = normalized.match(/^([a-z]:\/Users\/[^/]+)/i)
  if (win) return win[1]
  const unix = normalized.match(/^(\/home\/[^/]+)/i) || normalized.match(/^(\/Users\/[^/]+)/i)
  return unix?.[1] || null
}

function buildRequestedArtifactDescriptor(ctx: PlannerContext, targetDir: string): { path: string; fallbackPath: string; topic: string } {
  const topic = extractArtifactTopic(getEffectiveUserPrompt(ctx))
  const slug = slugifyAscii(topic || 'document')
  return {
    topic,
    path: joinWorkspacePath(targetDir, `${slug || 'document'}_revision.pdf`),
    fallbackPath: joinWorkspacePath(targetDir, 'aurora_revision.pdf'),
  }
}

function extractArtifactTopic(prompt: string): string {
  const normalized = normalizeIntentText(prompt)
  if (/\b(seconde|2e|deuxieme).{0,16}guerre.{0,16}mondiale\b/.test(normalized) || /\b(ww2|wwii)\b/.test(normalized)) {
    return 'seconde_guerre_mondiale'
  }
  const match = normalized.match(/\b(?:sur|a propos de|concernant)\s+(.{4,80}?)(?:\s+pour|\s+dans|\s+avec|$)/)
  if (match?.[1]) return match[1].trim()
  return 'document'
}

function slugifyAscii(value: string): string {
  return normalizeIntentText(value)
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 64)
}

function findLatestSuccessfulRead(history: PlannerContext['history'], path: string): PlannerContext['history'][number] | null {
  const normalized = normalizeWorkspacePath(path).toLowerCase()
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry.action.kind !== 'read_file' || !entry.result.ok) continue
    if (normalizeWorkspacePath(entry.action.path).toLowerCase() === normalized) return entry
  }
  return null
}

function findLatestActionForPath(
  history: PlannerContext['history'],
  kind: 'write_file' | 'read_file' | 'list_dir',
  path: string,
): PlannerContext['history'][number] | null {
  const normalized = normalizeWorkspacePath(path).toLowerCase()
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry.action.kind !== kind) continue
    if (!('path' in entry.action)) continue
    if (normalizeWorkspacePath(entry.action.path).toLowerCase() === normalized) return entry
  }
  return null
}

function findLatestListDirForPath(history: PlannerContext['history'], path: string): PlannerContext['history'][number] | null {
  const exact = findLatestActionForPath(history, 'list_dir', path)
  if (exact?.result.ok) return exact
  return null
}

function selectUserFolderReadableFiles(output: string, folderPath: string, userPrompt: string): string[] {
  const prompt = normalizeIntentText(userPrompt)
  const topicTokens = prompt
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 4 && !['dans', 'avec', 'pour', 'fichier', 'fichiers', 'dossier', 'bureau', 'document', 'controle'].includes(token))
  return parseUserFolderListing(output)
    .map((entry) => isAbsoluteWorkspacePath(entry) ? entry : joinWorkspacePath(folderPath, entry))
    .filter(isReadableUserNoteFile)
    .map((path) => ({ path, score: scoreUserFolderFile(path, topicTokens) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.path.localeCompare(b.path))
    .map((row) => row.path)
    .filter(uniqueString)
    .slice(0, 8)
}

function parseUserFolderListing(output: string): string[] {
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^(volume|directory of|repertoire de)\b/i.test(line))
    .filter((line) => !/^\d{2}\/\d{2}\/\d{4}/.test(line))
    .filter(uniqueString)
}

function buildUserFolderOverviewReply(target: UserFolderTarget, output: string): string {
  const entries = parseUserFolderListing(output)
  const files = entries.filter((entry) => !isLikelyDirectoryEntry(entry))
  const probableDirs = entries.filter(isLikelyDirectoryEntry)
  const extSummary = summarizeExtensions(files)
  const shown = entries.slice(0, 80)
  const hidden = Math.max(0, entries.length - shown.length)

  return [
    `## Topo du dossier ${target.label}`,
    '',
    `Chemin scanne : \`${target.path}\``,
    `Entrees detectees : **${entries.length}**`,
    `Fichiers probables : **${files.length}**`,
    `Dossiers probables / elements sans extension : **${probableDirs.length}**`,
    `Types de fichiers : ${extSummary || 'aucune extension evidente'}`,
    '',
    '## Contenu',
    shown.length > 0
      ? shown.map((entry) => `- ${formatUserFolderEntry(entry)}`).join('\n')
      : '- Le dossier semble vide ou inaccessible.',
    hidden > 0 ? `\n\n... ${hidden} autre(s) entree(s) non affichee(s).` : '',
    '',
    '## Lecture rapide',
    entries.length === 0
      ? '- Rien a trier pour l instant.'
      : '- Je me suis limite au topo demande : aucune creation de fichier n a ete relancee.',
  ].filter(Boolean).join('\n')
}

function isLikelyDirectoryEntry(entry: string): boolean {
  const clean = entry.trim()
  if (!clean) return false
  if (/^<DIR>/i.test(clean)) return true
  if (/[\\/]$/.test(clean)) return true
  const name = clean.split(/[\\/]/).pop() || clean
  return !/\.[a-z0-9]{1,8}$/i.test(name)
}

function formatUserFolderEntry(entry: string): string {
  const kind = isLikelyDirectoryEntry(entry) ? 'dossier probable' : 'fichier'
  return `\`${entry}\` (${kind})`
}

function isReadableUserNoteFile(path: string): boolean {
  const lower = normalizeWorkspacePath(path).toLowerCase()
  if (isSensitivePathName(lower)) return false
  return /\.(txt|md|markdown|csv|json|html|htm|rtf)$/i.test(lower)
}

function scoreUserFolderFile(path: string, topicTokens: string[]): number {
  const lower = normalizeIntentText(path)
  let score = 1
  if (/\b(cours|revision|controle|histoire|fiche|note|resume)\b/.test(lower)) score += 12
  for (const token of topicTokens) {
    if (lower.includes(token)) score += 8
  }
  return score
}

function isSensitivePathName(path: string): boolean {
  const lower = normalizeWorkspacePath(path).toLowerCase()
  return /(^|\/)(\.env|id_rsa|id_dsa|id_ecdsa|id_ed25519|credentials?|secrets?)(\.|\/|$)/.test(lower)
    || /\.(pem|key|p12|pfx|crt)$/i.test(lower)
}

function isAbsoluteWorkspacePath(path: string): boolean {
  return /^([a-z]:\/|\/)/i.test(normalizeWorkspacePath(path))
}

function joinWorkspacePath(base: string, child: string): string {
  return `${normalizeWorkspacePath(base).replace(/\/+$/, '')}/${normalizeWorkspacePath(child).replace(/^\/+/, '')}`
}

function buildStudyPdfContent(
  ctx: PlannerContext,
  target: UserFolderTarget,
  listing: PlannerContext['history'][number],
  outputPath: string,
): string {
  const files = parseUserFolderListing(listing.result.output || '')
  const readEntries = ctx.history.filter((entry) => entry.action.kind === 'read_file' && entry.result.ok)
  const descriptor = buildRequestedArtifactDescriptor(ctx, target.path)
  const topic = descriptor.topic === 'seconde_guerre_mondiale'
    ? 'Seconde Guerre mondiale'
    : descriptor.topic.replace(/_/g, ' ')
  const lines = buildStudyGuideLines(topic, target, files, readEntries, outputPath)
  return buildSimplePdf(lines)
}

function buildStudyGuideLines(
  topic: string,
  target: UserFolderTarget,
  files: string[],
  readEntries: PlannerContext['history'],
  outputPath: string,
): string[] {
  const sourceNames = readEntries
    .filter((entry) => entry.action.kind === 'read_file')
    .map((entry) => entry.action.kind === 'read_file' ? entry.action.path.split(/[\\/]/).pop() || entry.action.path : '')
    .filter(Boolean)
    .slice(0, 8)
  const lines = [
    `Fiche de revision - ${topic}`,
    `Cree par Aurora dans le dossier ${target.label}`,
    `Fichier verifie attendu : ${outputPath}`,
    '',
    `Scan du dossier : ${files.length} entree(s) detectee(s).`,
    sourceNames.length > 0
      ? `Notes locales lues : ${sourceNames.join(', ')}.`
      : 'Aucune note texte locale pertinente detectee : fiche construite comme support de revision autonome.',
    '',
    'Objectif controle',
    '- Savoir raconter les grandes phases du conflit avec des dates simples.',
    '- Expliquer les causes, les acteurs, la violence de masse et les consequences.',
    '- Repondre avec des exemples precis plutot que des phrases vagues.',
    '',
    'Dates essentielles',
    '- 1933 : Hitler arrive au pouvoir en Allemagne.',
    '- 1 septembre 1939 : invasion de la Pologne par l Allemagne.',
    '- 3 septembre 1939 : la France et le Royaume-Uni declarent la guerre.',
    '- 1940 : defaite francaise, armistice, appel du 18 juin.',
    '- 1941 : invasion de l URSS et entree en guerre des Etats-Unis apres Pearl Harbor.',
    '- 1942-1943 : tournant de la guerre, Stalingrad, El Alamein, Midway.',
    '- 6 juin 1944 : debarquement en Normandie.',
    '- 8 mai 1945 : capitulation allemande.',
    '- 6 et 9 aout 1945 : bombes atomiques sur Hiroshima et Nagasaki.',
    '- 2 septembre 1945 : capitulation japonaise.',
    '',
    'Causes principales',
    '- Le traite de Versailles est vecu comme une humiliation par beaucoup d Allemands.',
    '- La crise economique des annees 1930 favorise les regimes autoritaires.',
    '- Hitler veut agrandir l espace vital allemand et impose une politique raciste.',
    '- Les democraties reagissent trop tard aux agressions nazies et fascistes.',
    '',
    'Grandes phases',
    '1. 1939-1941 : victoires de l Axe. L Allemagne utilise la guerre eclair.',
    '2. 1941-1942 : mondialisation du conflit avec URSS et Etats-Unis.',
    '3. 1942-1943 : tournant militaire, les Allies reprennent l initiative.',
    '4. 1944-1945 : liberation de l Europe puis defaite du Japon.',
    '',
    'La France pendant la guerre',
    '- 1940 : la France est vaincue et coupee entre zone occupee et regime de Vichy.',
    '- Vichy collabore avec l Allemagne nazie.',
    '- De Gaulle organise la France libre depuis Londres.',
    '- La Resistance agit par renseignement, sabotage, journaux clandestins et maquis.',
    '- La liberation se fait progressivement apres les debarquements de 1944.',
    '',
    'Genocide et violence de masse',
    '- La Shoah est l extermination des Juifs d Europe par les nazis.',
    '- Les Tziganes sont aussi victimes d un genocide.',
    '- Les ghettos, fusillades, deportations et centres de mise a mort montrent une violence organisee par l Etat.',
    '- Auschwitz-Birkenau symbolise cette politique d extermination.',
    '',
    'Consequences',
    '- Bilan humain immense : environ 60 millions de morts.',
    '- L Europe est detruite et affaiblie.',
    '- Les Etats-Unis et l URSS deviennent les deux grandes puissances.',
    '- Creation de l ONU en 1945 pour eviter une nouvelle guerre mondiale.',
    '- Les proces de Nuremberg jugent les crimes nazis et definissent la notion de crime contre l humanite.',
    '',
    'Methode pour avoir tout bon',
    '- Toujours commencer par dater et situer.',
    '- Utiliser les mots cles : Axe, Allies, guerre totale, genocide, collaboration, Resistance, liberation.',
    '- Pour une question longue : faire cause -> evenement -> consequence.',
    '- Ajouter au moins un exemple precis : Stalingrad, Pearl Harbor, Normandie, Auschwitz, appel du 18 juin.',
    '',
    'Mini plan de reponse',
    'Introduction : La Seconde Guerre mondiale est un conflit mondial de 1939 a 1945.',
    'Partie 1 : Une guerre provoquee par les ambitions de l Axe.',
    'Partie 2 : Une guerre totale qui mobilise soldats, civils, economies et propagande.',
    'Partie 3 : Une guerre d aneantissement marquee par les genocides.',
    'Conclusion : Le monde sort transforme, avec l ONU et la domination USA/URSS.',
    '',
    'Auto-test',
    '1. Pourquoi la guerre commence-t-elle en 1939 ?',
    '2. Pourquoi 1942-1943 est-il un tournant ?',
    '3. Quelle est la difference entre collaboration et Resistance ?',
    '4. Pourquoi parle-t-on de guerre totale ?',
    '5. Qu est-ce qu un crime contre l humanite ?',
  ]

  for (const entry of readEntries.slice(0, 4)) {
    if (entry.action.kind !== 'read_file') continue
    const snippet = (entry.result.output || '').replace(/\s+/g, ' ').trim().slice(0, 240)
    if (snippet) {
      lines.push('', `Note locale prise en compte - ${entry.action.path.split(/[\\/]/).pop()}:`, snippet)
    }
  }
  return lines
}

function buildSimplePdf(rawLines: string[]): string {
  const wrapped = rawLines.flatMap((line) => wrapPdfLine(toPdfAscii(line), 92))
  const pages = chunkLines(wrapped, 44)
  const pageIds = pages.map((_, index) => 4 + index * 2)
  const objects: { id: number; body: string }[] = [
    { id: 1, body: '<< /Type /Catalog /Pages 2 0 R >>' },
    { id: 2, body: `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>` },
    { id: 3, body: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>' },
  ]
  for (let i = 0; i < pages.length; i += 1) {
    const pageId = pageIds[i]
    const contentId = pageId + 1
    const stream = buildPdfTextStream(pages[i])
    objects.push({
      id: pageId,
      body: `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`,
    })
    objects.push({
      id: contentId,
      body: `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    })
  }

  objects.sort((a, b) => a.id - b.id)
  let pdf = '%PDF-1.4\n'
  const offsets = ['0000000000 65535 f ']
  for (const object of objects) {
    offsets[object.id] = `${String(pdf.length).padStart(10, '0')} 00000 n `
    pdf += `${object.id} 0 obj\n${object.body}\nendobj\n`
  }
  const xrefOffset = pdf.length
  pdf += `xref\n0 ${objects.length + 1}\n`
  for (let i = 0; i <= objects.length; i += 1) {
    pdf += `${offsets[i] || '0000000000 00000 f '}\n`
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  return pdf
}

function buildPdfTextStream(lines: string[]): string {
  return [
    'BT',
    '/F1 11 Tf',
    '50 790 Td',
    '14 TL',
    ...lines.map((line) => `(${escapePdfText(line)}) Tj T*`),
    'ET',
  ].join('\n')
}

function toPdfAscii(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, '-')
    .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '')
}

function escapePdfText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function wrapPdfLine(line: string, width: number): string[] {
  if (!line.trim()) return ['']
  const words = line.split(/\s+/)
  const out: string[] = []
  let current = ''
  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length > width && current) {
      out.push(current)
      current = word
    } else {
      current = next
    }
  }
  if (current) out.push(current)
  return out
}

function chunkLines(lines: string[], size: number): string[][] {
  const chunks: string[][] = []
  for (let i = 0; i < lines.length; i += size) {
    chunks.push(lines.slice(i, i + size))
  }
  return chunks.length > 0 ? chunks : [['Document vide']]
}

function isWorkspaceExplorationRequest(ctx: PlannerContext): boolean {
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  if (isDesktopAnalysisRequest(ctx)) return false
  if (isUserFolderTargetRequest(ctx)) return false
  const wantsTraverse = /\b(navigue|naviguer|parcours|parcourir|explore|explorer|inspecte|inspecter|analyse|analyser|audite|auditer|lis|lire|regarde|scanner|scan|cartographie|resume|resumer)\b/.test(current)
  const targetsWorkspace = /\b(tous les fichiers|tout les fichiers|chaque fichier|fichiers|projet|repo|repository|workspace|codebase|dossier|arborescence|source|code)\b/.test(current)
  const asksAllFiles = /(tous|tout|chaque|ensemble).{0,24}fichier/.test(current)
    || /navigu\w*.{0,24}fichier/.test(current)
  return (wantsTraverse && targetsWorkspace) || asksAllFiles
}

function isCreativeApplyRequest(ctx: PlannerContext): boolean {
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  return /\b(creatif|creative|imagine|imaginer|invente|inventer|ameliore|ameliorer|applique|appliquer|implemente|implementer|modifie|modifier|refactor|corrige|fix|design|cree|creer|genere|generer|produis|produire)\b/.test(current)
}

function isCreativeReflectionRequest(ctx: PlannerContext): boolean {
  if (isDesktopAnalysisRequest(ctx)) return false
  const current = normalizeIntentText(getEffectiveUserPrompt(ctx))
  const asksCreative = /\b(creatif|creative|imagine|imaginer|invente|inventer|brainstorm|idee|idees|concept|direction|style|ambitieux|original|strategie|vision|reflechis|reflechir|propose)\b/.test(current)
  const wantsConcreteOutput = /\b(cree|creer|genere|generer|produis|produire|ameliore|ameliorer|concois|concevoir|design|ecris|redige|planifie|applique|appliquer|implemente|implementer|modifie|modifier)\b/.test(current)
  return asksCreative && (wantsConcreteOutput || current.length > 40)
}

function normalizeIntentText(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}

function findLatestWorkspaceInventory(history: PlannerContext['history']): PlannerContext['history'][number] | null {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (!entry.result.ok || !entry.result.output?.trim()) continue
    if (isWorkspaceInventoryShellAction(entry.action) || entry.action.kind === 'list_dir') {
      return entry
    }
  }
  return null
}

function isWorkspaceInventoryShellAction(action: CoworkAction): boolean {
  return action.kind === 'shell'
    && /(^|[\\/])rg(\.exe)?$/i.test(action.command.trim())
    && (action.args || []).includes('--files')
}

function countWorkspaceInventoryFailures(history: PlannerContext['history']): number {
  return history.filter((entry) => isWorkspaceInventoryShellAction(entry.action) && !entry.result.ok).length
}

function countWorkspaceReadActions(history: PlannerContext['history']): number {
  return history.filter((entry) => entry.action.kind === 'read_file').length
}

function hasReadWorkspacePath(history: PlannerContext['history'], path: string): boolean {
  const normalized = normalizeWorkspacePath(path).toLowerCase()
  return history.some((entry) => {
    if (entry.action.kind !== 'read_file') return false
    const readPath = normalizeWorkspacePath(entry.action.path).toLowerCase()
    return readPath === normalized || readPath.endsWith('/' + normalized)
  })
}

function selectWorkspaceFilesForReading(output: string, userPrompt: string): string[] {
  const files = parseWorkspaceFileList(output)
  const prompt = normalizeIntentText(userPrompt)
  const wantsCowork = /\bcowork\b/.test(prompt)
  const wantsFrontend = /\b(front|ui|interface|react|tsx|css|style|design)\b/.test(prompt)
  const wantsBackend = /\b(tauri|rust|backend|server|api|python|service)\b/.test(prompt)

  return files
    .filter(isLikelyReadableProjectFile)
    .map((path) => ({ path, score: scoreWorkspaceFile(path, { wantsCowork, wantsFrontend, wantsBackend }) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.path.length - b.path.length || a.path.localeCompare(b.path))
    .map((row) => row.path)
    .filter(uniqueString)
    .slice(0, 12)
}

function parseWorkspaceFileList(output: string): string[] {
  return output
    .split(/\r?\n/)
    .map(normalizeWorkspacePath)
    .filter((line) => !!line && !line.startsWith('__AURORA_'))
    .filter((line) => !line.includes('node_modules/') && !line.includes('/.git/'))
    .filter(uniqueString)
}

function normalizeWorkspacePath(path: string): string {
  return path
    .trim()
    .replace(/^["']|["']$/g, '')
    .replace(/\\/g, '/')
    .replace(/^\.\//, '')
}

function uniqueString(value: string, index: number, array: string[]): boolean {
  return array.indexOf(value) === index
}

function isLikelyReadableProjectFile(path: string): boolean {
  const lower = path.toLowerCase()
  if (!lower || lower.endsWith('/')) return false
  if (/(^|\/)(package-lock|pnpm-lock|yarn\.lock|cargo\.lock)$/.test(lower)) return false
  if (/(^|\/)(\.env|id_rsa|id_dsa|credentials|secrets?)(\.|$)/.test(lower)) return false
  if (/\.(png|jpe?g|gif|webp|ico|mp4|mov|mp3|wav|glb|gltf|dll|exe|zip|7z|tar|gz|pdf)$/i.test(lower)) return false
  return /\.(ts|tsx|js|jsx|mjs|cjs|json|md|mdx|rs|py|toml|ya?ml|css|scss|html|vue|svelte|sql|sh|ps1)$/i.test(lower)
    || /(^|\/)(readme|dockerfile|makefile|justfile|license)(\.|$)/i.test(lower)
}

function scoreWorkspaceFile(
  path: string,
  opts: { wantsCowork: boolean; wantsFrontend: boolean; wantsBackend: boolean },
): number {
  const lower = path.toLowerCase()
  let score = 1
  if (/(^|\/)(readme|package\.json|tsconfig.*\.json|vite\.config|cargo\.toml|pyproject\.toml|tauri\.conf\.json)/.test(lower)) score += 90
  if (/(^|\/)src\/(app|main|index)\.(tsx|ts|jsx|js)$/.test(lower)) score += 70
  if (/(^|\/)(app|main|index)\.(tsx|ts|jsx|js|rs|py)$/.test(lower)) score += 45
  if (lower.includes('/services/')) score += 35
  if (lower.includes('/components/')) score += 28
  if (lower.includes('/__tests__/') || lower.includes('.test.')) score += 22
  if (opts.wantsCowork && lower.includes('cowork')) score += 120
  if (opts.wantsFrontend && /\.(tsx|jsx|css|scss|html)$/.test(lower)) score += 45
  if (opts.wantsBackend && /\.(rs|py|ts)$/.test(lower)) score += 40
  if (lower.includes('/dist/') || lower.includes('/build/') || lower.includes('/output/')) score -= 80
  return score
}

function buildWorkspaceExplorationReply(
  ctx: PlannerContext,
  inventory: PlannerContext['history'][number],
): string | null {
  const files = parseWorkspaceFileList(inventory.result.output || '')
  if (files.length === 0) return null
  const readEntries = ctx.history.filter((entry) => entry.action.kind === 'read_file' && entry.result.ok)
  const extCounts = summarizeExtensions(files)
  const topDirs = summarizeTopDirectories(files)
  const readSummary = readEntries.slice(-12).map(summarizeReadEntry).join('\n\n')

  return [
    '## Carte du workspace',
    '',
    `- Fichiers detectes : **${files.length}**`,
    `- Dossiers principaux : ${topDirs || 'non deduits'}`,
    `- Types dominants : ${extCounts || 'non deduits'}`,
    '',
    '## Fichiers pivots lus',
    readSummary || '- Aucun fichier pivot n a encore pu etre lu.',
    '',
    '## Lecture operationnelle',
    '- Je n ai pas demande a l utilisateur de coller les fichiers : ils ont ete parcourus via les outils locaux.',
    '- Pour une suite creative ou une modification, le prochain passage doit partir de ces fichiers lus, appliquer le changement, puis verifier par lecture/test/build.',
  ].join('\n')
}

function summarizeExtensions(files: string[]): string {
  const counts = new Map<string, number>()
  for (const file of files) {
    const match = file.match(/\.([a-z0-9]+)$/i)
    const ext = match ? `.${match[1].toLowerCase()}` : '(sans ext)'
    counts.set(ext, (counts.get(ext) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([ext, count]) => `${ext} ${count}`)
    .join(', ')
}

function summarizeTopDirectories(files: string[]): string {
  const counts = new Map<string, number>()
  for (const file of files) {
    const dir = file.includes('/') ? file.split('/')[0] : '.'
    counts.set(dir, (counts.get(dir) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([dir, count]) => `${dir}/ ${count}`)
    .join(', ')
}

function summarizeReadEntry(entry: PlannerContext['history'][number]): string {
  if (entry.action.kind !== 'read_file') return ''
  const output = entry.result.output || ''
  const lines = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  const interesting = lines
    .filter((line) => /^(import|export|function|class|const|let|type|interface|#|\/\/|describe\(|test\()/.test(line))
    .slice(0, 6)
  const preview = (interesting.length > 0 ? interesting : lines.slice(0, 5))
    .join(' ')
    .slice(0, 500)
  return `- **${entry.action.path}** (${output.length} octets) : ${preview || 'contenu vide ou non textuel.'}`
}

async function planWithRetry(
  systemPrompt: string,
  userPrompt: string,
  retriesLeft: number,
  signal?: AbortSignal,
  ctx?: PlannerContext,
): Promise<CoworkPlan> {
  const model = useAppStore.getState().mainModel
  const response = await ollamaChat(
    model,
    [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    undefined,
    { signal, num_ctx: 32000, firstByteTimeoutMs: 900_000 },
  )
  // ollamaChat returns the full Ollama response object: { message: { content }, ... }.
  // We extract the assistant's text content so parsePlan gets a string.
  const raw = extractContent(response)
  const parsed = parsePlan(raw)
  if (parsed.ok) {
    // postProcessPlan : si le plan est "lecture seule + finish", strip le
    // finish pour forcer une iteration #2 de synthese. Sinon, normalise en
    // s assurant qu il finit par finish.
    let processed = postProcessPlan(parsed.plan)
    // v82ly — auto-emit extract_structured(card_iteration) when the prior
    // analyze_page in history reports pageType.social_feed=true with strong
    // topological signals (>=5 repeating cards). Pure post-processor — the
    // LLM's plan stays intact when the gate doesn't fire. ZERO selectors
    // hardcoded, just the topological hints (repeating_card_count,
    // has_avatars, has_timestamps, has_reactions) propagated through to the
    // bridge so the LLM extractor can structure its per-card output.
    if (ctx) {
      processed = injectCardIterationFollowUp(processed, ctx.history)
    }
    processed = repairMetaOnlyReplyPlan(processed, ctx)
    processed = repairExtensionBlockedWebResearchPlan(processed, ctx)
    processed = repairPassiveCoworkPlan(processed, ctx)
    return processed
  }
  if (retriesLeft > 0) {
    // Stronger repair prompt : be very directive about the schema. Mention
    // the exact failure mode and remind the 3 mandatory keys.
    const repairPrompt = [
      `Ton dernier output etait INVALIDE : ${parsed.error}.`,
      ``,
      `Tu DOIS produire un objet JSON unique avec EXACTEMENT 3 cles obligatoires :`,
      `  - "reasoning": string (1-3 phrases)`,
      `  - "actions": tableau d objets {kind: ...}`,
      `  - "expectedOutcome": string`,
      ``,
      `Pas de markdown. Pas de prose autour. Pas de commentaires.`,
      `Si tu ne sais pas, pose une question concrete en reply + finish. N ecris pas une meta-analyse du type "il faudrait consulter".`,
      ``,
      `Demande utilisateur originale: ${userPrompt}`,
    ].join('\n')
    return planWithRetry(systemPrompt, repairPrompt, retriesLeft - 1, signal, ctx)
  }

  // ---------------------------------------------------------------------
  // v23 — FINAL FALLBACK STAGE : retries are exhausted and the LLM still
  // can't emit valid JSON. Aurora MUST NOT abandon. We do 3 progressively
  // simpler attempts in order :
  //
  //   1. Plain-text answer extraction : if the raw response contains any
  //      coherent prose (which is almost always the case even when the
  //      JSON is malformed), wrap the longest readable chunk into a
  //      single reply action. Aurora at least answers something useful.
  //
  //   2. Ultra-minimal LLM call : ask the LLM in 2 lines to emit JUST
  //      `{ "actions": [{"kind":"reply","message":"<your answer>"}], ... }`.
  //      No system prompt clutter — minimal context, max compliance.
  //
  //   3. History-based deterministic synthesis (already existed).
  //
  //   4. Polite "I couldn't" only if all else fails.
  // ---------------------------------------------------------------------

  // Stage 1 : try to salvage prose from the malformed JSON output.
  const salvaged = salvageProseFromMalformedJson(raw)
  if (salvaged) {
    return repairExtensionBlockedWebResearchPlan(repairMetaOnlyReplyPlan({
      reasoning: 'Le modele n a pas produit du JSON valide mais le contenu textuel est exploitable.',
      actions: [
        { kind: 'reply', message: salvaged },
        { kind: 'finish', summary: 'Reponse extraite du texte brut malgre JSON invalide.' },
      ],
      expectedOutcome: 'User a une reponse exploitable malgre l erreur de format.',
    }, ctx), ctx)
  }

  // Stage 2 : ultra-minimal retry with a stripped-down ask.
  try {
    const minimalResp = await ollamaChat(
      model,
      [{ role: 'user', content: `Reponds a cette question utilisateur en JSON STRICT : { "actions": [{"kind":"reply","message":"TA REPONSE ICI"}, {"kind":"finish","summary":"fait"}], "reasoning":"r", "expectedOutcome":"o" }\n\nQuestion : ${ctx?.userPrompt || userPrompt}` }],
      undefined,
      { signal, num_ctx: 32000, firstByteTimeoutMs: 900_000 },
    )
    const minimalRaw = extractContent(minimalResp)
    const minimalParsed = parsePlan(minimalRaw)
    if (minimalParsed.ok) return repairExtensionBlockedWebResearchPlan(repairMetaOnlyReplyPlan(postProcessPlan(minimalParsed.plan), ctx), ctx)
    // Even the minimal failed — try to salvage prose from THIS response too.
    const minimalSalvage = salvageProseFromMalformedJson(minimalRaw)
    if (minimalSalvage) {
      return repairExtensionBlockedWebResearchPlan(repairMetaOnlyReplyPlan({
        reasoning: 'Salvage du minimal-retry.',
        actions: [
          { kind: 'reply', message: minimalSalvage },
          { kind: 'finish', summary: 'Reponse extraite du minimal-retry.' },
        ],
        expectedOutcome: 'User a une reponse.',
      }, ctx), ctx)
    }
  } catch { /* ignore — fall through */ }

  // ---------------------------------------------------------------------
  // RESILIENT FALLBACK : retries are exhausted. Instead of abandoning,
  // we synthesise a deterministic reply from whatever USABLE data is in
  // the execution history. This is the "Aurora never gives up" rule.
  //
  // Priority :
  //  1. If history contains an HTML fetch/browser result → use the digest
  //  2. If history contains a connector / file read → format result preview
  //  3. Otherwise → polite reply pointing to user prompt
  // ---------------------------------------------------------------------
  if (ctx && ctx.history.length > 0) {
    const fallback = buildResilientFallbackReply(ctx.history)
    if (fallback) {
      return {
        reasoning: 'Le modele n a pas produit de plan JSON exploitable, mais l historique contient des donnees utiles. Synthese deterministe basee sur ces donnees.',
        actions: [
          { kind: 'reply', message: fallback },
          { kind: 'finish', summary: 'Synthese deterministe rendue (LLM en panne).' },
        ],
        expectedOutcome: 'User a une reponse exploitable malgre l echec du LLM.',
      }
    }
  }
  return {
    reasoning: 'Le modele n a pas produit de plan JSON valide et l historique est vide ou inutilisable.',
    actions: [
      { kind: 'reply', message: `Desole, je n ai pas reussi a structurer une reponse exploitable. Reformule la demande en restant precis. (Erreur planner: ${parsed.error})` },
      { kind: 'finish', summary: 'Plan abandonne — JSON invalide.' },
    ],
    expectedOutcome: 'Aucun changement.',
  }
}

// ---------------------------------------------------------------------------
// Prompt builders
// ---------------------------------------------------------------------------

function buildSystemPrompt(ctx: PlannerContext): string {
  const enabledCaps = ctx.capabilities
    .filter((c) => c.enabled)
    .map((c) => `- ${c.label} (id=${c.id})${c.destructive ? ' [destructif]' : ''}`)
    .join('\n')

  const settings = loadSettings()
  const userPersona = ctx.voiceMode ? settings.systemPromptVoice : settings.systemPromptText
  const moduleContext = ctx.module ? settings.contextByModule[ctx.module] : ''
  const teamSection = buildCoworkTeamPromptSection(ctx.module)
  // Connecteurs actives + flag quotaExhausted (depuis le dernier test/run).
  const PUBLIC_NO_KEY: ReadonlyArray<string> = ['wikipedia', 'arxiv', 'hackernews', 'reddit']
  const enabledList = Object.entries(settings.connectors)
    .filter(([id, c]) => c.enabled && (c.apiKey || PUBLIC_NO_KEY.includes(id)))
    .map(([id, c]) => {
      const exhausted = !!(c.lastCheck && !c.lastCheck.ok && /quota|exhausted|429|402|limit/i.test(c.lastCheck.message || ''))
      return { id: id as keyof typeof CONNECTORS, quotaExhausted: exhausted, hasKey: !!c.apiKey }
    })
  const enabledConnectors = buildConnectorBriefForLLM(
    enabledList.map((e) => ({ id: e.id, quotaExhausted: e.quotaExhausted })),
  )
  const opsCatalog = enabledList
    .map((e) => {
      const meta = CONNECTORS[e.id]
      const ops = meta?.actions.map((a) => a.name).join(', ') ?? ''
      return `- ${e.id}: ${ops}`
    })
    .join('\n')

  // v16 — User memory : facts the user has explicitly told Aurora to
  // remember. Surfaced here so plans can be personalized without re-asking.
  // Capped at 30 lines so the prompt stays compact ; the most recent facts
  // win (the persistence layer enforces an LRU of MAX_MEMORY=50 entries).
  const memorySection = settings.userMemory.length > 0
    ? '\n## Faits memorises sur l utilisateur (utilise pour personnaliser tes plans, surtout les choix par defaut quand le user ne precise pas) :\n'
      + settings.userMemory.slice(-30).map((e) => `- ${e.fact}${e.tags?.length ? ` [${e.tags.join('|')}]` : ''}`).join('\n')
      + '\n\nQuand l user te dit explicitement "retiens que…", "souviens-toi…", "n oublie pas que…" → emets remember_fact. Quand il dit "oublie…", "supprime de ta memoire…" → emets forget_fact.'
    : ''

  // v21 — Conversation continuity : derniers tours de chat user/Aurora.
  // Permet aux follow-up questions ("approfondis", "et la version mobile ?",
  // "mais en code", "pareil pour la prod") de fonctionner naturellement.
  // Cap a ~5 tours et chaque message tronque a 600 chars pour eviter de
  // saturer le contexte LLM.
  const recentTurns = (ctx.conversationHistory ?? []).slice(-10)
  const conversationSection = recentTurns.length > 0
    ? '\n## Conversation recente (derniers tours, du plus ancien au plus recent) :\n'
      + recentTurns.map((t) => {
          const who = t.role === 'user' ? 'USER' : 'AURORA'
          const text = (t.content || '').replace(/\s+/g, ' ').trim().slice(0, 600)
          return `[${who}] ${text}${t.content && t.content.length > 600 ? '…' : ''}`
        }).join('\n')
      + '\n\nUtilise ces tours pour resoudre les references implicites de la nouvelle question (pronoms, "ca", "la meme", "approfondis", "donc", "et la version X", etc). Le DERNIER message user reste prioritaire : s il demande un nouveau livrable ou une analyse differente, ne repete pas l ancienne action. Ne reexecute les memes actions que si le user le demande explicitement.'
    : ''

  // v29 — attached image descriptions : the overlay already ran vision on
  // each user-attached image and passes the descriptions here. Surface
  // them in the prompt as factual context — the planner uses them when
  // formulating the reply (no need to re-run vision).
  const imagesSection = (ctx.attachedImageDescriptions && ctx.attachedImageDescriptions.length > 0)
    ? `\n## Images jointes par l user (${ctx.attachedImageDescriptions.length} description${ctx.attachedImageDescriptions.length > 1 ? 's' : ''}) :
L user a joint des images au message. La vision a deja ete analysee par qwen3-vl. Voici les descriptions :
${ctx.attachedImageDescriptions.map((d, i) => `\n### Image ${i + 1}\n${d.slice(0, 1500)}${d.length > 1500 ? '\n…[tronque]' : ''}`).join('\n')}

Utilise ces descriptions comme contexte factuel pour repondre a la question de l user. Cite les elements precis vus (texte, couleurs, layout, chiffres, erreurs visibles, etc) plutot que d evoquer "l image" en abstrait.`
    : ''

  // v28 — voice mode : when ON, Aurora MUST chain a voice_speak (TTS Kokoro)
  // before each finish so replies are read aloud. The text must be short
  // (1-2 sentences max), conversational, no markdown — destined to be spoken.
  const voiceSection = ctx.voiceMode
    ? `\n## Mode VOCAL ACTIF — REGLE OBLIGATOIRE :
Avant CHAQUE finish, tu DOIS emettre une action voice_speak qui resume oralement la reponse en 1-2 phrases COURTES, conversationnelles, SANS markdown (pas de \\n, pas de ##, pas de listes), parfaite pour etre lue a voix haute par TTS Kokoro.
Exemple : si reply contient un long rapport markdown, voice_speak peut etre "J ai analyse la page : 3 sections principales, 5 KPIs, et un score global de 78%. Tu veux le detail par section ?"
Le voice_speak passe APRES le reply (qui sert pour l affichage texte) et AVANT le finish. Garde voice_speak.text < 300 caracteres pour rester naturel a l ecoute.`
    : ''

  // v82m1 — token-aware visual-retry nudge. Pure prompt enrichment, only
  // appended when the most-recent extract_structured(card_iteration) flagged
  // under_extraction:true on a page whose analyze_page reported visual
  // signals (avatars or reactions). Returns null otherwise → ZERO token
  // overhead in the normal case. Educational, not imperative — the planner
  // can ignore it if its judgement says otherwise.
  const visualRetryNudge = buildVisualRetryNudge(ctx.history)

  // v82m6 — user-pinned connectors propagation. When the user has pinned
  // one or more connectors via the AuditDrawer promote-CTA, surface them in
  // the system prompt as a single-line educational hint. The LLM may
  // consider but is free to ignore if the action doesn't match the context.
  // Pure : empty / undefined input → empty string → ZERO token overhead.
  const pinnedHint = _buildPinnedConnectorsHint(ctx.pinnedConnectorIds)

  // v82m6 — DUAL_SIGNAL_INEFFECTIVE fallback. When the current host has
  // proven that the screenshot+includeImage escalation strategy doesn't
  // change extraction quality (>=5 emitted, 0 accepted per
  // `dual-signal-effective` endpoint), suggest a STRATEGY change rather
  // than another retry of the same path. Empty / undefined → no line.
  // v82m8 — tier-2 (TREND) ineffective hosts threaded in alongside tier-1.
  // When BOTH tiers are ineffective for the current host, the helper emits
  // the terminal TIER_3 nudge ; otherwise existing tier-1 / tier-2 fallback
  // strings preserved.
  const ineffectiveHint = _buildIneffectiveHostHint(ctx.ineffectiveHosts, ctx.history, ctx.trendIneffectiveHosts)
  const conversationFrame = resolveCoworkConversationFrame(ctx.userPrompt, ctx.conversationHistory)
  const conversationFrameSection = buildCoworkConversationSection(conversationFrame)
  const projectThreadSection = buildCoworkProjectThreadSection(ctx.projectThread)
  const missionSection = buildMissionContractSection({
    prompt: conversationFrame.effectivePrompt || ctx.userPrompt,
    runtime: ctx.runtime,
    history: ctx.history,
  })

  return [
    userPersona || 'Tu es Aurora.',
    '',
    'Tu es en mode COWORK. Tu produis un PLAN JSON exploitable par un executeur deterministe.',
    '',
    teamSection,
    `Runtime actif: ${ctx.runtime}.`,
    `Workspace racine: ${ctx.workspaceRoot || '(non defini)'}`,
    moduleContext ? `\nContexte module: ${moduleContext}` : '',
    pinnedHint,
    memorySection,
    conversationSection,
    conversationFrameSection,
    imagesSection,
    projectThreadSection,
    voiceSection,
    `\nCapacites activees:\n${enabledCaps || '(aucune)'}`,
    '',
    missionSection,
    enabledConnectors ? `\nConnecteurs externes disponibles (action "connector") — utilise le bon outil pour chaque besoin :\n${enabledConnectors}\n\nActions exposees (id: actions):\n${opsCatalog}` : '',
    '',
    PLAN_SCHEMA,
    '',
    ACTION_CATALOG,
    '',
    PLANNER_RULES,
    '',
    PLAN_EXAMPLES,
    '',
    visualRetryNudge ? visualRetryNudge : '',
    ineffectiveHint,
    `Boucle: max ${SAFETY_LIMITS.maxPlanIterations} iterations. Termine par "finish" des que l objectif est atteint.`,
  ].join('\n')
}

function repairPassiveCoworkPlan(plan: CoworkPlan, ctx?: PlannerContext): CoworkPlan {
  if (!ctx) return plan
  const frame = resolveCoworkConversationFrame(ctx.userPrompt, ctx.conversationHistory)
  if (!frame.shouldExecute) return plan
  const activeActions = plan.actions.filter((action) => action.kind !== 'finish' && action.kind !== 'voice_speak')
  const hasRealTool = activeActions.some((action) => !['reply', 'think'].includes(action.kind))
  if (hasRealTool) return plan
  const bootstrap = buildMissionBootstrapPlan(ctx)
  if (!bootstrap) return plan
  return {
    ...bootstrap,
    reasoning: `${bootstrap.reasoning} Le plan LLM initial etait passif alors que la demande exige une action.`,
  }
}

// v82m6 — pin propagation + ineffective-host helpers live in
// coworkPlanParser.ts (leaf module, no Vite imports) so they can be unit-
// tested under `node --experimental-strip-types --test`. Re-exported below
// for backward-compat with any caller that imports them from coworkPlanner.
export { buildPinnedConnectorsHint, buildIneffectiveHostHint } from './coworkPlanParser.ts'

function buildUserPrompt(ctx: PlannerContext): string {
  const effectivePrompt = getEffectiveUserPrompt(ctx).trim()
  const lines: string[] = [`Demande utilisateur: ${ctx.userPrompt.trim()}`]
  if (effectivePrompt && effectivePrompt !== ctx.userPrompt.trim()) {
    lines.push('', `Objectif effectif Cowork: ${effectivePrompt}`)
  }
  if ((ctx.conversationHistory ?? []).length > 0) {
    lines.push(
      '',
      'Instruction de continuite: utilise la conversation recente pour comprendre les references implicites, mais classe toujours l intention du DERNIER message avant de reprendre une ancienne tache.',
    )
  }
  const clarificationHint = buildClarificationContinuationHint(ctx.userPrompt, ctx.conversationHistory)
  if (clarificationHint) {
    lines.push('', clarificationHint)
  }
  if (ctx.history.length > 0) {
    lines.push('', 'Historique d execution (pour reflechir au prochain pas) :')
    for (const entry of ctx.history.slice(-6)) {
      const summary = summariseEntry(entry)
      lines.push(`- ${summary}`)
    }
  }
  return lines.join('\n')
}

function summariseEntry(entry: { action: CoworkAction; result: CoworkActionResult; under_extraction?: boolean }): string {
  // v82m0 — surface the per-card under_extraction telemetry to the LLM so the
  // next iteration can naturally choose to retry (e.g. with includeImage:true
  // for media-heavy pages). Suffix is short on purpose ; the LLM picks up
  // the cue without us spelling out the retry strategy.
  const underExt = entry.under_extraction
    ? ' [under_extraction:true — items.length < cards_processed*0.5, consider retry with includeImage:true]'
    : ''
  const outcome = (entry.result.ok ? 'OK' : `KO (${entry.result.error || '?'})`) + underExt
  const kind = entry.action.kind
  // Inclure le contenu utile du resultat pour que le LLM puisse vraiment
  // raisonner dessus sur l iteration suivante. Sinon il ne voit que "OK"
  // et synthetise du vide.
  const dataSnippet = formatResultDataForLLM(entry.action, entry.result)
  switch (kind) {
    case 'read_file':
      return `read_file ${entry.action.path} → ${outcome} (${entry.result.output?.length ?? 0} octets)\n${dataSnippet}`
    case 'list_dir':
      return `list_dir ${entry.action.path} → ${outcome}\n${dataSnippet}`
    case 'write_file':
      return `write_file ${entry.action.path} → ${outcome}`
    case 'edit_file':
      return `edit_file ${entry.action.path} → ${outcome}`
    case 'delete_file':
      return `delete_file ${entry.action.path} → ${outcome}`
    case 'shell':
      return `shell ${entry.action.command} ${(entry.action.args ?? []).join(' ')} → ${outcome}\n${dataSnippet}`
    case 'web_search':
      return `web_search "${entry.action.query}" -> ${outcome}\n${dataSnippet}`
    case 'fetch':
      return `fetch ${entry.action.url} → ${outcome}\n${dataSnippet}`
    case 'open_url':
      return `open_url ${entry.action.url} → ${outcome}`
    case 'clipboard_read':
      return `clipboard_read → ${outcome}\n${dataSnippet}`
    case 'clipboard_write':
      return `clipboard_write → ${outcome}`
    case 'voice_speak':
      return `voice_speak (${entry.action.text.length} chars) → ${outcome}`
    case 'dom_query':
      return `dom_query ${entry.action.selector} → ${outcome}\n${dataSnippet}`
    case 'think':
      return `think (${entry.action.topic}) → ${outcome}\n   note: ${entry.action.thought.slice(0, 500)}`
    case 'think_long':
      return `think_long (${entry.action.topic}) → ${outcome}\n${dataSnippet}`
    case 'remember_fact':
      return `remember_fact ("${entry.action.fact.slice(0, 80)}") → ${outcome}`
    case 'forget_fact':
      return `forget_fact (${entry.action.id ?? `match="${entry.action.matching}"`}) → ${outcome}`
    case 'vision_describe':
      return `vision_describe → ${outcome}\n${dataSnippet}`
    case 'screenshot_desktop':
      return `screenshot_desktop → ${outcome}\n${dataSnippet}`
    case 'connector':
      return `connector ${entry.action.connector}.${entry.action.action} → ${outcome}\n${dataSnippet}`
    case 'browser':
      return `browser ${entry.action.operation}${entry.action.payload ? ' ' + JSON.stringify(entry.action.payload).slice(0, 80) : ''} → ${outcome}\n${dataSnippet}`
    case 'reply':
      return `reply (${(entry.action.message || '').slice(0, 60)}…) → ${outcome}`
    case 'finish':
      return `finish (${(entry.action.summary || '').slice(0, 60)}…) → ${outcome}`
    default:
      return `${(entry.action as { kind: string }).kind} → ${outcome}`
  }
}

// Format the actual data the executor returned so the LLM can build a real
// answer on top. We cap heavily to keep tokens reasonable.
const RESULT_PREVIEW_BYTES = 2000

function formatResultDataForLLM(action: CoworkAction, result: CoworkActionResult): string {
  if (!result.ok && result.error) {
    return `   erreur: ${result.error.slice(0, 400)}`
  }
  // Special case : screenshot returns a HUGE base64 dataUrl that would saturate
  // the LLM context. We replace it with a marker so the LLM knows a screenshot
  // is available and can chain `vision_describe` to actually analyze it.
  if (action.kind === 'browser' && action.operation === 'screenshot' && result.data) {
    const d = result.data as { dataUrl?: string; length?: number }
    const sizeKB = d.dataUrl ? Math.round(d.dataUrl.length / 1024) : 0
    return `   screenshot: dataUrl PNG base64 capturee (${sizeKB} KB). Pour l analyser visuellement, chaine une action vision_describe avec imageDataUrl=<la dataUrl>. Ne mets PAS la dataUrl entiere dans ton plan, le bridge la retrouvera depuis l historique.`
  }
  // v115 — screenshot_desktop : meme mecanisme, on cache la dataUrl entiere
  // pour ne pas saturer le contexte LLM.
  if (action.kind === 'screenshot_desktop' && result.data) {
    const d = result.data as { dataUrl?: string; path?: string; sizeKB?: number }
    return `   screenshot_desktop: ${d.sizeKB ?? 0} KB capturee, path=${d.path || '?'}. Pour l analyser, chaine vision_describe avec imageDataUrl=<la dataUrl du screenshot_desktop> — le bridge retrouvera la dataUrl complete dans l historique.`
  }
  // For vision_describe, the data is already a text description : keep it.
  if (action.kind === 'vision_describe' && result.data) {
    const d = result.data as { description?: string }
    if (d.description) {
      const desc = d.description.length > RESULT_PREVIEW_BYTES
        ? d.description.slice(0, RESULT_PREVIEW_BYTES) + `\n…[tronque · ${d.description.length - RESULT_PREVIEW_BYTES} octets]`
        : d.description
      return `   description vision:\n${indent(desc, 4)}`
    }
  }
  // For think_long, the structured "reasoning" field holds the full LLM-generated
  // analysis. Keep it but allow a wider budget (4 KB) since this is the whole
  // point of the action — the synthesis pass needs the actual reflection.
  if (action.kind === 'think_long' && result.data) {
    const d = result.data as { reasoning?: string; topic?: string; model?: string }
    if (d.reasoning) {
      const cap = 4000
      const r = d.reasoning.length > cap
        ? d.reasoning.slice(0, cap) + `\n…[tronque · ${d.reasoning.length - cap} octets]`
        : d.reasoning
      return `   think_long [${d.model || 'local'}] sur "${d.topic || ''}":\n${indent(r, 4)}`
    }
  }
  // === Special case : raw HTML responses ===
  // When fetch / read_html / read_dom / open_url return HTML, the first 2KB
  // is usually <head>+boilerplate (links, meta, fonts) and the LLM cannot
  // synthesise from it. We extract a structured DIGEST (title, headings,
  // meta description, paragraphs, links, images) — same shape browser.analyze_page
  // produces, but client-side from the raw markup.
  const isHtmlAction = action.kind === 'fetch'
    || (action.kind === 'browser' && (action.operation === 'read_html' || action.operation === 'read_dom'))
  if (isHtmlAction) {
    const raw = (typeof result.output === 'string' ? result.output : '')
      || (typeof result.data === 'string' ? result.data : '')
    if (raw && /<\s*(html|!doctype)/i.test(raw.slice(0, 200))) {
      const digest = extractHtmlDigest(raw)
      return `   digest HTML (extrait du markup brut, ${(raw.length / 1024).toFixed(1)} KB original) :\n${indent(digest, 4)}`
    }
  }

  // Prefer structured data when present (lists, JSON), fall back to output.
  if (result.data !== undefined && result.data !== null) {
    let serialized: string
    try { serialized = JSON.stringify(result.data, null, 2) } catch { serialized = String(result.data) }
    if (serialized.length > RESULT_PREVIEW_BYTES) {
      serialized = serialized.slice(0, RESULT_PREVIEW_BYTES) + `\n…[tronque · ${serialized.length - RESULT_PREVIEW_BYTES} octets]`
    }
    return `   resultat:\n${indent(serialized, 4)}`
  }
  if (result.output) {
    let out = result.output
    if (out.length > RESULT_PREVIEW_BYTES) {
      out = out.slice(0, RESULT_PREVIEW_BYTES) + `\n…[tronque · ${out.length - RESULT_PREVIEW_BYTES} octets]`
    }
    return `   sortie:\n${indent(out, 4)}`
  }
  return ''
}

function indent(s: string, n: number): string {
  const pad = ' '.repeat(n)
  return s.split('\n').map((l) => pad + l).join('\n')
}


// Parsing + plan utility logic (ensureFinishAction, planSignature) lives in
// coworkPlanParser.ts so it can be unit-tested without pulling in the
// LLM-driven planner.

// ---------------------------------------------------------------------------
// extractContent — robustly turn whatever ollamaChat returned into a plain
// string the parser can work with. Ollama returns `{message: {content}}` in
// the new API but older servers / proxies sometimes return just the string
// or `{response: ...}`.
// ---------------------------------------------------------------------------

function extractContent(response: unknown): string {
  if (typeof response === 'string') return response
  if (!response || typeof response !== 'object') return String(response ?? '')
  const r = response as Record<string, unknown>
  // Ollama chat: { message: { content: "..." } }
  if (r.message && typeof r.message === 'object') {
    const m = r.message as Record<string, unknown>
    if (typeof m.content === 'string') return m.content
  }
  // Ollama generate: { response: "..." }
  if (typeof r.response === 'string') return r.response
  // OpenAI-style: { choices: [{ message: { content } }] }
  if (Array.isArray(r.choices) && r.choices.length > 0) {
    const c0 = r.choices[0] as Record<string, unknown>
    const cm = c0?.message as Record<string, unknown> | undefined
    if (cm && typeof cm.content === 'string') return cm.content
    if (typeof c0?.text === 'string') return c0.text as string
  }
  // Last resort : stringify (parser will fail cleanly with "no JSON detected")
  try { return JSON.stringify(response) } catch { return String(response) }
}
