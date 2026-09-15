// ---------------------------------------------------------------------------
// coworkConnectors — registry of ~30 external services Aurora can call.
// Every connector exposes:
//   - meta : id, label, description, env keys, action catalog, doc URL
//   - test : hits a cheap auth endpoint to verify the API key
//   - run  : executes a typed action and returns a structured payload
// ---------------------------------------------------------------------------

import type { ConnectorId } from './coworkSettings.ts'
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'

// v83 — resolve the Flask bridge base. In the Tauri desktop app the WebView
// origin is NOT the bridge, so relative '/api/...' would not reach Flask :
// use the local absolute URL. In web/cloud, getBridgeUrl() returns '' (Vite /
// tunnel proxy forwards) or the explicit local URL.
function bridgeBase(): string {
  if (isTauriRuntime()) return 'http://127.0.0.1:3001'
  return getBridgeUrl()
}

export type ConnectorMeta = {
  id: ConnectorId
  label: string
  description: string
  apiKeyLabel: string
  apiKeyHelp: string
  docUrl: string
  category: 'dev' | 'cloud' | 'productivity' | 'communication' | 'calendar-mail' | 'storage' | 'media' | 'iot' | 'data' | 'ai' | 'design' | 'commerce' | 'misc'
  actions: ReadonlyArray<{ name: string; description: string }>
  needsWorkspaceId?: boolean
  // Semantic metadata pour le LLM : il sait POURQUOI ce connecteur existe.
  purpose?: string                           // 1 phrase, "a quoi sert ce service"
  whenToUse?: ReadonlyArray<string>          // mots-cles + use cases qui declenchent l usage
  // Fallback local si le service externe est indisponible / quota epuise.
  // Le planner traduit "use openai" en "use ollama avec mainModel" quand
  // openai.lastCheck.message contient quota_exhausted.
  fallback?: {
    kind: 'local-module' | 'local-llm' | 'connector'
    target: string                          // 'image' | 'three-d' | 'mainModel' | 'ollama' | 'huggingface' | etc.
    note: string                            // 1 phrase pour le LLM
  }
  freeTier?: string                         // ex: "200 generations gratuites/mois", "free tier 5K req/mois"
}

export type ConnectorTestResult = {
  ok: boolean
  message: string
  user?: string
}

export type ConnectorRunResult = {
  ok: boolean
  data?: unknown
  output?: string
  error?: string
}

const CT_JSON = { 'Content-Type': 'application/json' }

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const CONNECTORS: Record<ConnectorId, ConnectorMeta> = {
  // === DEV / CLOUD ===
  github: {
    id: 'github', label: 'GitHub', category: 'dev',
    description: 'Repos, issues, PRs, releases, GitHub Actions + logs CI.',
    purpose: 'Hebergement de code source, issues, pull requests, automation CI + lecture des logs Actions.',
    whenToUse: ['repo', 'depot', 'pull request', 'PR', 'issue', 'commit', 'branche', 'release', 'github action', 'workflow', 'CI logs', 'failure logs', 'run logs', 'merge', 'fork'],
    freeTier: 'Gratuit pour repos publics + 2000 min Actions/mois.',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://github.com/settings/tokens — scopes: repo, workflow, actions:read.',
    docUrl: 'https://docs.github.com/en/rest',
    actions: [
      { name: 'list_repos', description: 'Liste les depots' },
      { name: 'get_repo', description: 'Details d un repo (owner/repo)' },
      { name: 'list_issues', description: 'Liste les issues d un repo' },
      { name: 'create_issue', description: 'Cree une issue (destructif)' },
      { name: 'list_prs', description: 'Liste les PRs' },
      { name: 'merge_pr', description: 'Merge une PR (destructif)' },
      { name: 'search_code', description: 'Recherche dans le code' },
      { name: 'list_workflows', description: 'Liste les workflows Actions d un repo' },
      { name: 'list_workflow_runs', description: 'Runs d un workflow (status, conclusion, branch)' },
      { name: 'get_run_logs', description: 'Logs textuels d un run (zip transforme en texte)' },
      { name: 'rerun_workflow', description: 'Relance un run en echec (destructif)' },
    ],
  },
  gitlab: {
    id: 'gitlab', label: 'GitLab', category: 'dev',
    description: 'Projets, issues, MRs, CI GitLab.',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://gitlab.com/-/profile/personal_access_tokens — scope: api.',
    docUrl: 'https://docs.gitlab.com/ee/api/',
    actions: [
      { name: 'list_projects', description: 'Liste tes projets' },
      { name: 'list_issues', description: 'Issues d un projet' },
      { name: 'create_issue', description: 'Cree une issue' },
    ],
  },
  vercel: {
    id: 'vercel', label: 'Vercel', category: 'cloud',
    description: 'Liste/deploiement de projets, environnements, logs.',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://vercel.com/account/tokens (full access).',
    docUrl: 'https://vercel.com/docs/rest-api',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_projects', description: 'Projets Vercel' },
      { name: 'create_deployment', description: 'Lance un deploiement (destructif)' },
      { name: 'list_deployments', description: 'Historique deploiements' },
    ],
  },
  netlify: {
    id: 'netlify', label: 'Netlify', category: 'cloud',
    description: 'Sites, deploys, env vars Netlify.',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://app.netlify.com/user/applications#personal-access-tokens',
    docUrl: 'https://docs.netlify.com/api/get-started/',
    actions: [
      { name: 'list_sites', description: 'Liste tes sites Netlify' },
      { name: 'get_site', description: 'Details d un site' },
      { name: 'list_deploys', description: 'Deploys d un site' },
    ],
  },
  cloudflare: {
    id: 'cloudflare', label: 'Cloudflare', category: 'cloud',
    description: 'Zones DNS, Workers, Pages, R2.',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://dash.cloudflare.com/profile/api-tokens (template "Read all"+ permissions custom selon besoin).',
    docUrl: 'https://developers.cloudflare.com/api/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_zones', description: 'Zones DNS' },
      { name: 'list_workers', description: 'Workers deployes' },
      { name: 'purge_cache', description: 'Purge cache d une zone (destructif)' },
    ],
  },
  render: {
    id: 'render', label: 'Render.com', category: 'cloud',
    description: 'Services + deploys Render.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://dashboard.render.com/u/settings#api-keys',
    docUrl: 'https://api-docs.render.com/',
    actions: [
      { name: 'list_services', description: 'Services deployes' },
      { name: 'trigger_deploy', description: 'Force un nouveau deploy (destructif)' },
    ],
  },
  railway: {
    id: 'railway', label: 'Railway.app', category: 'cloud',
    description: 'Projets + services Railway via GraphQL.',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://railway.app/account/tokens',
    docUrl: 'https://docs.railway.app/reference/public-api',
    actions: [
      { name: 'list_projects', description: 'Tes projets Railway' },
    ],
  },
  fly: {
    id: 'fly', label: 'Fly.io', category: 'cloud',
    description: 'Apps + machines Fly.io.',
    apiKeyLabel: 'Auth Token',
    apiKeyHelp: 'flyctl auth token, ou cle generee sur https://fly.io/user/personal_access_tokens',
    docUrl: 'https://fly.io/docs/machines/api/',
    actions: [
      { name: 'list_apps', description: 'Apps Fly' },
      { name: 'list_machines', description: 'Machines d une app' },
    ],
  },
  supabase: {
    id: 'supabase', label: 'Supabase', category: 'cloud',
    description: 'DB Postgres + Storage + Auth Supabase via REST.',
    apiKeyLabel: 'Service Role Key',
    apiKeyHelp: 'Project Settings -> API. Inclure baseUrl https://<project>.supabase.co.',
    docUrl: 'https://supabase.com/docs/reference/api',
    needsWorkspaceId: false,
    actions: [
      { name: 'select', description: 'SELECT sur une table (params: table, query)' },
      { name: 'insert', description: 'INSERT (destructif)' },
      { name: 'rpc', description: 'Appel d une fonction Postgres' },
    ],
  },

  // === PRODUCTIVITY / DOCS ===
  notion: {
    id: 'notion', label: 'Notion', category: 'productivity',
    description: 'Pages + databases Notion.',
    apiKeyLabel: 'Integration Token',
    apiKeyHelp: 'https://www.notion.so/my-integrations puis partage les pages cibles.',
    docUrl: 'https://developers.notion.com/',
    actions: [
      { name: 'search', description: 'Recherche dans le workspace' },
      { name: 'get_page', description: 'Lit une page' },
      { name: 'create_page', description: 'Cree une page (destructif)' },
      { name: 'query_db', description: 'Interroge une DB' },
    ],
  },
  linear: {
    id: 'linear', label: 'Linear', category: 'productivity',
    description: 'Issues, sprints, projets, time tracking Linear.',
    purpose: 'Issue tracking ergonomique pour equipes produit + suivi du temps passe par issue.',
    whenToUse: ['linear', 'issue produit', 'sprint', 'roadmap', 'time tracking', 'temps passe', 'estimate', 'history issue'],
    freeTier: 'Free plan 250 issues',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://linear.app/settings/api',
    docUrl: 'https://developers.linear.app/',
    actions: [
      { name: 'list_issues', description: 'Tes issues' },
      { name: 'create_issue', description: 'Cree une issue (destructif)' },
      { name: 'update_issue', description: 'Modifie une issue (destructif)' },
      { name: 'get_issue_history', description: 'Historique d une issue (etats, comments, transitions)' },
      { name: 'list_time_entries', description: 'Time entries d une issue (estimate + comments timestamps)' },
      { name: 'add_comment', description: 'Ajoute un commentaire (utile pour log temps : "30min : refactor X")' },
    ],
  },
  asana: {
    id: 'asana', label: 'Asana', category: 'productivity',
    description: 'Taches + projets Asana.',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://app.asana.com/0/my-apps',
    docUrl: 'https://developers.asana.com/',
    actions: [
      { name: 'list_tasks', description: 'Tes taches' },
      { name: 'create_task', description: 'Nouvelle tache' },
    ],
  },
  todoist: {
    id: 'todoist', label: 'Todoist', category: 'productivity',
    description: 'Taches Todoist (une todo-list legendaire).',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://todoist.com/app/settings/integrations -> Developer.',
    docUrl: 'https://developer.todoist.com/rest/v2/',
    actions: [
      { name: 'list_tasks', description: 'Liste les taches actives' },
      { name: 'create_task', description: 'Ajoute une tache' },
      { name: 'close_task', description: 'Marque une tache comme faite' },
    ],
  },

  // === COMMUNICATION ===
  slack: {
    id: 'slack', label: 'Slack', category: 'communication',
    description: 'Messages + channels Slack via Bot Token.',
    apiKeyLabel: 'Bot User OAuth Token',
    apiKeyHelp: 'https://api.slack.com/apps -> ton app -> OAuth & Permissions (xoxb-...).',
    docUrl: 'https://api.slack.com/web',
    actions: [
      { name: 'send_message', description: 'Envoie un message dans un channel (destructif)' },
      { name: 'list_channels', description: 'Liste les channels' },
    ],
  },
  discord: {
    id: 'discord', label: 'Discord', category: 'communication',
    description: 'Messages + channels via webhook ou bot token.',
    apiKeyLabel: 'Bot Token',
    apiKeyHelp: 'Cree une app sur https://discord.com/developers/applications puis copie le bot token.',
    docUrl: 'https://discord.com/developers/docs',
    actions: [
      { name: 'send_message', description: 'Envoie dans un channel (destructif)' },
      { name: 'list_guilds', description: 'Liste tes serveurs' },
    ],
  },
  telegram: {
    id: 'telegram', label: 'Telegram Bot', category: 'communication',
    description: 'Bot Telegram via BotFather.',
    apiKeyLabel: 'Bot Token (BotFather)',
    apiKeyHelp: 'https://t.me/BotFather puis /newbot.',
    docUrl: 'https://core.telegram.org/bots/api',
    actions: [
      { name: 'send_message', description: 'Envoie un message a un chat_id (destructif)' },
      { name: 'get_updates', description: 'Liste les messages recents' },
    ],
  },

  // === CALENDAR / MAIL ===
  gcal: {
    id: 'gcal', label: 'Google Calendar', category: 'calendar-mail',
    description: 'Lecture + creation d evenements via OAuth bearer.',
    apiKeyLabel: 'OAuth Access Token',
    apiKeyHelp: 'https://developers.google.com/calendar/api/quickstart — colle l access_token (refresh manuel, on n implemente pas le flow OAuth ici).',
    docUrl: 'https://developers.google.com/calendar/api/v3/reference',
    actions: [
      { name: 'list_events', description: 'Evenements a venir' },
      { name: 'create_event', description: 'Cree un evt (destructif)' },
    ],
  },
  gmail: {
    id: 'gmail', label: 'Gmail', category: 'calendar-mail',
    description: 'Lecture + envoi de mail via Gmail API.',
    apiKeyLabel: 'OAuth Access Token',
    apiKeyHelp: 'https://developers.google.com/gmail/api/quickstart',
    docUrl: 'https://developers.google.com/gmail/api/reference/rest',
    actions: [
      { name: 'list_messages', description: 'Liste tes derniers mails' },
      { name: 'send', description: 'Envoie un mail (destructif)' },
    ],
  },

  // === STORAGE ===
  gdrive: {
    id: 'gdrive', label: 'Google Drive', category: 'storage',
    description: 'Fichiers Drive via OAuth bearer.',
    apiKeyLabel: 'OAuth Access Token',
    apiKeyHelp: 'https://developers.google.com/drive/api/quickstart',
    docUrl: 'https://developers.google.com/drive/api/v3/reference',
    actions: [
      { name: 'list_files', description: 'Tes fichiers' },
      { name: 'download', description: 'Telecharge un fichier' },
    ],
  },
  dropbox: {
    id: 'dropbox', label: 'Dropbox', category: 'storage',
    description: 'Fichiers Dropbox.',
    apiKeyLabel: 'Access Token',
    apiKeyHelp: 'https://www.dropbox.com/developers/apps -> ton app -> Generate access token.',
    docUrl: 'https://www.dropbox.com/developers/documentation/http/documentation',
    actions: [
      { name: 'list_folder', description: 'Contenu d un dossier' },
      { name: 'get_account', description: 'Info compte (test connexion)' },
    ],
  },

  // === MEDIA ===
  spotify: {
    id: 'spotify', label: 'Spotify', category: 'media',
    description: 'Lecture / playlists / recherche Spotify + Spotify Connect (changer d enceinte).',
    apiKeyLabel: 'OAuth Access Token',
    apiKeyHelp: 'https://developer.spotify.com/dashboard — flow Authorization Code, copie le access_token. Scopes recommandes : user-modify-playback-state user-read-playback-state playlist-read-private.',
    docUrl: 'https://developer.spotify.com/documentation/web-api',
    actions: [
      { name: 'me', description: 'Profil utilisateur (test connexion)' },
      { name: 'search', description: 'Recherche tracks/albums/artists' },
      { name: 'play', description: 'Lance une lecture (destructif — change l etat)' },
      { name: 'pause', description: 'Met en pause' },
      { name: 'next', description: 'Track suivante' },
      { name: 'list_playlists', description: 'Tes playlists' },
      { name: 'list_devices', description: 'Liste les appareils Spotify Connect (PC, telephone, enceinte)' },
      { name: 'transfer_playback', description: 'Bascule la lecture sur un autre appareil (params: device_id, play?)' },
      { name: 'set_volume', description: 'Volume 0-100 (params: volume_percent, device_id?)' },
    ],
  },
  youtube: {
    id: 'youtube', label: 'YouTube Data API', category: 'media',
    description: 'Recherche videos + channels YouTube.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://console.cloud.google.com/ -> Activer YouTube Data API v3 -> Credentials.',
    docUrl: 'https://developers.google.com/youtube/v3/docs',
    actions: [
      { name: 'search', description: 'Recherche videos' },
      { name: 'video_details', description: 'Details + stats video' },
    ],
  },

  // === IoT ===
  home_assistant: {
    id: 'home_assistant', label: 'Home Assistant', category: 'iot',
    description: 'Domotique : lumieres, capteurs, scenes Home Assistant.',
    apiKeyLabel: 'Long-lived access token',
    apiKeyHelp: 'Profil Home Assistant -> Long-lived access tokens. baseUrl = http://homeassistant.local:8123 (ou ton IP).',
    docUrl: 'https://developers.home-assistant.io/docs/api/rest/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_states', description: 'Liste toutes les entites' },
      { name: 'call_service', description: 'Appelle un service (light.turn_on, scene.turn_on, etc.)' },
      { name: 'get_state', description: 'Etat d une entite specifique' },
    ],
  },
  philips_hue: {
    id: 'philips_hue', label: 'Philips Hue (local)', category: 'iot',
    description: 'Lumieres Hue via le bridge local.',
    apiKeyLabel: 'Username (Hue API)',
    apiKeyHelp: 'Cree un user via PUT au bridge https://developers.meethue.com/develop/get-started-2/. baseUrl = http://<bridge-ip>',
    docUrl: 'https://developers.meethue.com/develop/hue-api/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_lights', description: 'Lumieres connues' },
      { name: 'set_light', description: 'on/off/brightness/color' },
    ],
  },

  // === DATA / SEARCH ===
  openweather: {
    id: 'openweather', label: 'OpenWeather', category: 'data',
    description: 'Meteo actuelle + previsions.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://openweathermap.org/api -> Sign up.',
    docUrl: 'https://openweathermap.org/api',
    actions: [
      { name: 'current', description: 'Meteo actuelle (params: q ou lat/lon)' },
      { name: 'forecast', description: 'Previsions 5 jours' },
    ],
  },
  translate_deepl: {
    id: 'translate_deepl', label: 'DeepL', category: 'data',
    description: 'Traduction qualite premium DeepL.',
    apiKeyLabel: 'API Key (Free ou Pro)',
    apiKeyHelp: 'https://www.deepl.com/pro-api',
    docUrl: 'https://developers.deepl.com/docs',
    actions: [
      { name: 'translate', description: 'Traduit text vers target_lang' },
      { name: 'usage', description: 'Quota restant' },
    ],
  },
  maps_google: {
    id: 'maps_google', label: 'Google Maps', category: 'data',
    description: 'Geocoding + directions Google Maps.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://console.cloud.google.com/ -> Maps Platform.',
    docUrl: 'https://developers.google.com/maps/documentation',
    actions: [
      { name: 'geocode', description: 'Adresse -> coordonnees' },
      { name: 'directions', description: 'Itineraire entre 2 points' },
    ],
  },
  wikipedia: {
    id: 'wikipedia', label: 'Wikipedia', category: 'data',
    description: 'Recherche + extrait Wikipedia (pas de cle requise).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'Wikipedia est public — laisse vide ou mets "n/a" pour activer.',
    docUrl: 'https://www.mediawiki.org/wiki/API:Main_page',
    actions: [
      { name: 'search', description: 'Recherche articles' },
      { name: 'extract', description: 'Resume d un article' },
    ],
  },
  arxiv: {
    id: 'arxiv', label: 'arXiv', category: 'data',
    description: 'Recherche papiers de recherche arXiv (gratuit, public).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'arXiv est public — mets "n/a" pour activer.',
    docUrl: 'https://info.arxiv.org/help/api/index.html',
    actions: [
      { name: 'search', description: 'Recherche papiers (params: query, max_results)' },
    ],
  },
  hackernews: {
    id: 'hackernews', label: 'Hacker News', category: 'data',
    description: 'Top stories + recherche HN (gratuit).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'HN est public — mets "n/a" pour activer.',
    docUrl: 'https://github.com/HackerNews/API',
    actions: [
      { name: 'top', description: 'Top stories' },
      { name: 'search', description: 'Recherche via Algolia HN' },
    ],
  },
  reddit: {
    id: 'reddit', label: 'Reddit (read-only)', category: 'data',
    description: 'Lecture des posts Reddit (pas de cle, endpoint .json public).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'Reddit JSON public — mets "n/a" pour activer. Pour ecrire, OAuth requis (pas implemente).',
    docUrl: 'https://www.reddit.com/dev/api',
    actions: [
      { name: 'list_subreddit', description: 'Posts d un subreddit (params: subreddit, sort)' },
      { name: 'search', description: 'Recherche cross-subreddit' },
    ],
  },
  huggingface: {
    id: 'huggingface', label: 'Hugging Face', category: 'ai',
    description: 'Recherche modeles + Inference API.',
    apiKeyLabel: 'User Access Token',
    apiKeyHelp: 'https://huggingface.co/settings/tokens',
    docUrl: 'https://huggingface.co/docs/api-inference/quicktour',
    actions: [
      { name: 'search_models', description: 'Recherche modeles (params: search)' },
      { name: 'inference', description: 'Inference (params: model, inputs)' },
    ],
  },
  replicate: {
    id: 'replicate', label: 'Replicate', category: 'ai',
    description: 'Predictions Replicate (image gen, etc.).',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://replicate.com/account/api-tokens',
    docUrl: 'https://replicate.com/docs/reference/http',
    actions: [
      { name: 'list_models', description: 'Liste les modeles' },
      { name: 'create_prediction', description: 'Lance une prediction' },
    ],
  },
  stable_horde: {
    id: 'stable_horde', label: 'Stable Horde (free)', category: 'ai',
    description: 'Generation d images crowd-sourced gratuite.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://stablehorde.net/register — anonyme = "0000000000".',
    docUrl: 'https://stablehorde.net/api/',
    actions: [
      { name: 'generate_async', description: 'Lance une generation' },
      { name: 'check_status', description: 'Statut d une generation' },
    ],
  },
  brave_search: {
    id: 'brave_search', label: 'Brave Search', category: 'data',
    description: 'Recherche web Brave (independante, respectueuse vie privee).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://brave.com/search/api/',
    docUrl: 'https://api.search.brave.com/app/documentation',
    actions: [
      { name: 'web', description: 'Recherche web' },
      { name: 'news', description: 'News recentes' },
    ],
  },

  // === DESIGN ===
  canva: {
    id: 'canva', label: 'Canva', category: 'design',
    description: 'Designs Canva via Connect API.',
    apiKeyLabel: 'OAuth Access Token',
    apiKeyHelp: 'https://www.canva.dev/docs/connect/ — flow OAuth.',
    docUrl: 'https://www.canva.dev/docs/connect/',
    actions: [
      { name: 'list_designs', description: 'Liste tes designs' },
      { name: 'get_design', description: 'Details d un design' },
      { name: 'export_design', description: 'Exporte en PNG/PDF' },
    ],
  },
  figma: {
    id: 'figma', label: 'Figma', category: 'design',
    description: 'Lecture de fichiers Figma + commentaires.',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://www.figma.com/settings -> Personal access tokens.',
    docUrl: 'https://www.figma.com/developers/api',
    actions: [
      { name: 'me', description: 'Profil (test connexion)' },
      { name: 'get_file', description: 'Lit un fichier (params: file_key)' },
      { name: 'list_comments', description: 'Commentaires d un fichier' },
    ],
  },

  // === COMMERCE ===
  stripe: {
    id: 'stripe', label: 'Stripe', category: 'commerce',
    description: 'Customers, charges, subscriptions Stripe.',
    apiKeyLabel: 'Secret Key',
    apiKeyHelp: 'https://dashboard.stripe.com/apikeys — sk_live_... ou sk_test_...',
    docUrl: 'https://stripe.com/docs/api',
    actions: [
      { name: 'list_customers', description: 'Liste les customers' },
      { name: 'list_charges', description: 'Charges recentes' },
      { name: 'list_subscriptions', description: 'Abonnements actifs' },
    ],
  },

  // === INFRA / DATA PLANE ===
  postgres: {
    id: 'postgres', label: 'PostgreSQL', category: 'dev',
    description: 'Execute des requetes SQL sur ta base PostgreSQL via le bridge local.',
    apiKeyLabel: 'DSN (postgres://user:pass@host:5432/db)',
    apiKeyHelp: 'Le bridge se connecte avec psycopg2. Le DSN ne quitte jamais ta machine.',
    docUrl: 'https://www.postgresql.org/docs/',
    actions: [
      { name: 'query',  description: 'SELECT / aggregations (params: sql, args[])' },
      { name: 'exec',   description: 'INSERT/UPDATE/DELETE/DDL (destructif)' },
      { name: 'tables', description: 'Liste les tables du schema public' },
    ],
  },
  redis_upstash: {
    id: 'redis_upstash', label: 'Redis (Upstash REST)', category: 'dev',
    description: 'Cache + pub/sub Redis via l API REST Upstash.',
    apiKeyLabel: 'REST Token',
    apiKeyHelp: 'console.upstash.com -> ton DB -> REST API. baseUrl = https://<db>.upstash.io',
    docUrl: 'https://upstash.com/docs/redis/features/restapi',
    needsWorkspaceId: true,
    actions: [
      { name: 'get',  description: 'GET cle' },
      { name: 'set',  description: 'SET cle valeur (destructif)' },
      { name: 'del',  description: 'DEL cle (destructif)' },
      { name: 'keys', description: 'KEYS pattern' },
      { name: 'incr', description: 'INCR cle' },
    ],
  },
  s3: {
    id: 's3', label: 'S3 / MinIO / R2 / Backblaze', category: 'cloud',
    description: 'Stockage objets compatible S3 (AWS, MinIO, Cloudflare R2, Backblaze B2). Signature SigV4 cote bridge.',
    apiKeyLabel: 'AccessKey:SecretKey',
    apiKeyHelp: 'Format <access_key>:<secret_key>. baseUrl = endpoint S3 (ex: https://s3.amazonaws.com).',
    docUrl: 'https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_buckets',  description: 'Liste les buckets' },
      { name: 'list_objects',  description: 'Liste objets d un bucket' },
      { name: 'put_object',    description: 'Upload un objet (destructif)' },
      { name: 'delete_object', description: 'Supprime un objet (destructif)' },
    ],
  },
  tailscale: {
    id: 'tailscale', label: 'Tailscale', category: 'cloud',
    description: 'VPN mesh : voir tes machines, ACLs, key auth.',
    apiKeyLabel: 'API Key (tskey-api-...)',
    apiKeyHelp: 'login.tailscale.com/admin/settings/keys -> Generate API key.',
    docUrl: 'https://tailscale.com/api',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_devices', description: 'Machines de ton tailnet' },
      { name: 'get_device',   description: 'Details d une machine' },
      { name: 'list_keys',    description: 'Cles d auth' },
    ],
  },
  plausible: {
    id: 'plausible', label: 'Plausible Analytics', category: 'data',
    description: 'Stats web Plausible (vues, sources, pages, conversions).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'plausible.io/settings -> API keys. baseUrl = ton site_id (ex: example.com).',
    docUrl: 'https://plausible.io/docs/stats-api',
    needsWorkspaceId: true,
    actions: [
      { name: 'aggregate', description: 'Stats agregees (visitors, pageviews, bounce_rate)' },
      { name: 'breakdown', description: 'Breakdown par dimension (sources, pages, country)' },
      { name: 'realtime',  description: 'Visiteurs en ce moment' },
    ],
  },
  pushover: {
    id: 'pushover', label: 'Pushover', category: 'communication',
    description: 'Notifications push instantanees vers ton mobile (iOS/Android/desktop).',
    apiKeyLabel: 'AppToken:UserKey',
    apiKeyHelp: 'pushover.net/apps/build pour app token + pushover.net pour user key. Format <app>:<user>.',
    docUrl: 'https://pushover.net/api',
    actions: [
      { name: 'notify', description: 'Envoie une notif (params: message, title?, priority?, url?)' },
    ],
  },
  twilio: {
    id: 'twilio', label: 'Twilio (SMS / WhatsApp / appels)', category: 'communication',
    description: 'Envoi SMS, WhatsApp, declenche un appel vocal.',
    apiKeyLabel: 'AccountSID:AuthToken',
    apiKeyHelp: 'console.twilio.com -> Account info. Format AC<sid>:<token>. Numero From dans baseUrl.',
    docUrl: 'https://www.twilio.com/docs/api',
    needsWorkspaceId: true,
    actions: [
      { name: 'send_sms',      description: 'Envoie un SMS (params: to, body) — destructif' },
      { name: 'send_whatsapp', description: 'WhatsApp via Twilio (whatsapp:+<num>) — destructif' },
      { name: 'make_call',     description: 'Lance un appel TwiML (params: to, url) — destructif' },
    ],
  },
  openstreetmap: {
    id: 'openstreetmap', label: 'OpenStreetMap (Nominatim)', category: 'data',
    description: 'Geocoding gratuit Nominatim (alternative libre Google Maps).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'OSM Nominatim public. Mets "n/a". Respecte fair-use : max 1 req/s.',
    docUrl: 'https://nominatim.org/release-docs/latest/api/Overview/',
    actions: [
      { name: 'search',  description: 'Geocoding adresse -> coords' },
      { name: 'reverse', description: 'Reverse geocoding coords -> adresse' },
    ],
  },

  // === CYBER / OSINT ===
  hibp: {
    id: 'hibp', label: 'Have-I-Been-Pwned', category: 'data',
    description: 'Verifie si un email/password apparait dans une fuite de donnees.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://haveibeenpwned.com/API/Key — 3.50 USD/mois.',
    docUrl: 'https://haveibeenpwned.com/API/v3',
    actions: [
      { name: 'breached_account',  description: 'Liste des leaks pour un email' },
      { name: 'pwned_password',    description: 'Verifie un password (k-anonymity, pas de cle)' },
      { name: 'all_breaches',      description: 'Toutes les breach connues' },
    ],
  },
  abuseipdb: {
    id: 'abuseipdb', label: 'AbuseIPDB', category: 'data',
    description: 'Reputation IP (signalements abus, scans, brute-force).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://www.abuseipdb.com/account/api — gratuit 1000 req/jour.',
    docUrl: 'https://docs.abuseipdb.com/',
    actions: [
      { name: 'check',     description: 'Score abuse + categories signalees pour une IP' },
      { name: 'blacklist', description: 'Liste IPs blacklistees (top 10K)' },
      { name: 'report',    description: 'Reporte une IP comme abusive (destructif)' },
    ],
  },

  // === CULTURE / LOISIRS ===
  discogs: {
    id: 'discogs', label: 'Discogs (musique)', category: 'data',
    description: 'Catalogue exhaustif d albums vinyles + CDs (recherche, prix, releases).',
    apiKeyLabel: 'Personal Access Token',
    apiKeyHelp: 'https://www.discogs.com/settings/developers — token gratuit.',
    docUrl: 'https://www.discogs.com/developers',
    actions: [
      { name: 'search',         description: 'Recherche releases/artists/labels' },
      { name: 'release',        description: 'Details d une release (params: id)' },
      { name: 'artist',         description: 'Discographie d un artiste' },
    ],
  },
  igdb: {
    id: 'igdb', label: 'IGDB (jeux video)', category: 'data',
    description: 'Base IGDB : 200K+ jeux video, dev studios, plateformes, scores.',
    apiKeyLabel: 'ClientID:Bearer',
    apiKeyHelp: 'IGDB exige Twitch OAuth. Cree app sur https://dev.twitch.tv/console puis genere bearer token. Format <client_id>:<bearer>.',
    docUrl: 'https://api-docs.igdb.com/',
    actions: [
      { name: 'search_games', description: 'Recherche jeux par nom' },
      { name: 'top_rated',    description: 'Top jeux par rating' },
      { name: 'platforms',    description: 'Liste des plateformes' },
    ],
  },
  openlibrary: {
    id: 'openlibrary', label: 'Open Library (livres)', category: 'data',
    description: 'Catalogue de livres + ebooks gratuits (alternative libre Google Books).',
    apiKeyLabel: '(aucune)',
    apiKeyHelp: 'Open Library est public et gratuit. Mets "n/a" pour activer.',
    docUrl: 'https://openlibrary.org/developers/api',
    actions: [
      { name: 'search',  description: 'Recherche livres (title/author/isbn)' },
      { name: 'book',    description: 'Details d un livre par ISBN' },
      { name: 'author',  description: 'Bibliographie d un auteur' },
    ],
  },

  // === IMAGE GEN PREMIUM ===
  stability_ai: {
    id: 'stability_ai', label: 'Stability AI', category: 'ai',
    description: 'Generation d images Stable Diffusion 3 / Ultra / Core via l API officielle.',
    apiKeyLabel: 'API Key (sk-...)',
    apiKeyHelp: 'https://platform.stability.ai/account/keys — 25 credits gratuits a l inscription.',
    docUrl: 'https://platform.stability.ai/docs/api-reference',
    actions: [
      { name: 'generate_sd3',   description: 'Genere une image SD3 (params: prompt, aspect_ratio?)' },
      { name: 'generate_ultra', description: 'Genere une image Ultra (qualite max, params: prompt)' },
      { name: 'upscale',        description: 'Upscale 4x une image (params: image_b64)' },
    ],
  },

  // === MAPS LIBRE PREMIUM ===
  mapbox: {
    id: 'mapbox', label: 'Mapbox', category: 'data',
    description: 'Geocoding, directions, tiles vectorielles Mapbox (alt premium a Google Maps + plus rapide qu OSM).',
    apiKeyLabel: 'Public Token (pk.eyJ...)',
    apiKeyHelp: 'https://account.mapbox.com/access-tokens — gratuit 50K req/mois.',
    docUrl: 'https://docs.mapbox.com/api/',
    actions: [
      { name: 'geocode',     description: 'Adresse -> coords' },
      { name: 'reverse',     description: 'Coords -> adresse' },
      { name: 'directions',  description: 'Itineraire (params: profile, coords[])' },
    ],
  },

  // === FINANCE / CRYPTO ===
  coingecko: {
    id: 'coingecko', label: 'CoinGecko (crypto)', category: 'data',
    description: 'Prix crypto + historiques + market cap (gratuit, sans cle pour les usages basiques).',
    apiKeyLabel: '(aucune ou Pro Key)',
    apiKeyHelp: 'API publique gratuite : 10-30 req/min sans cle. Pour Pro : https://www.coingecko.com/en/api/pricing.',
    docUrl: 'https://www.coingecko.com/en/api/documentation',
    actions: [
      { name: 'simple_price',   description: 'Prix actuel (params: ids[], vs_currencies[])' },
      { name: 'market_chart',   description: 'Historique de prix (params: id, vs_currency, days)' },
      { name: 'trending',       description: 'Top 7 cryptos trending sur 24h' },
      { name: 'global',         description: 'Stats globales du marche crypto' },
    ],
  },
  polygon: {
    id: 'polygon', label: 'Polygon.io (stocks/forex/crypto)', category: 'data',
    description: 'Donnees marche US : actions, options, forex, crypto. Snapshot temps reel + historique.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://polygon.io/dashboard/api-keys — free tier 5 req/min.',
    docUrl: 'https://polygon.io/docs',
    actions: [
      { name: 'ticker_details',  description: 'Details d un ticker (params: ticker)' },
      { name: 'snapshot',        description: 'Snapshot temps reel d un ticker' },
      { name: 'aggregates',      description: 'OHLC historique (params: ticker, multiplier, timespan, from, to)' },
      { name: 'list_tickers',    description: 'Liste les tickers disponibles' },
    ],
  },

  // === OBSERVABILITY / ERRORS ===
  datadog: {
    id: 'datadog', label: 'Datadog (metrics + logs)', category: 'cloud',
    description: 'Lecture metriques/logs/monitors Datadog (US ou EU).',
    apiKeyLabel: 'API Key:Application Key',
    apiKeyHelp: 'https://app.datadoghq.com/organization-settings/api-keys + application-keys. Format <api>:<app>. baseUrl = https://api.datadoghq.com (ou .eu).',
    docUrl: 'https://docs.datadoghq.com/api/latest/',
    needsWorkspaceId: true,
    actions: [
      { name: 'query_metric', description: 'Query metric (params: query, from, to)' },
      { name: 'list_monitors', description: 'Liste les monitors Datadog' },
      { name: 'list_logs',     description: 'Recherche logs (params: query, from, to, limit)' },
      { name: 'create_event',  description: 'Cree un event Datadog (destructif)' },
    ],
  },
  habitica: {
    id: 'habitica', label: 'Habitica (gamification todo)', category: 'productivity',
    description: 'Transforme tes habitudes/taches en jeu RPG. Score+, monstres, recompenses.',
    apiKeyLabel: 'UserId:ApiToken',
    apiKeyHelp: 'https://habitica.com/user/settings/api — copie User ID + API Token. Format <userid>:<token>.',
    docUrl: 'https://habitica.com/apidoc/',
    actions: [
      { name: 'list_tasks',  description: 'Tes habitudes/dailies/todos' },
      { name: 'create_task', description: 'Cree une tache (params: type, text, priority?)' },
      { name: 'score_up',    description: 'Marque une tache comme faite (+gold +xp)' },
      { name: 'user_stats',  description: 'Stats RPG : niveau, gold, exp, hp, mp' },
    ],
  },
  algolia: {
    id: 'algolia', label: 'Algolia (search)', category: 'cloud',
    description: 'Search engine SaaS pour ton site/app : index + recherche instantanee + facets.',
    apiKeyLabel: 'AppID:SearchApiKey',
    apiKeyHelp: 'https://www.algolia.com/account/api-keys/ — Application ID + Search-Only API Key. Format <appid>:<key>.',
    docUrl: 'https://www.algolia.com/doc/',
    needsWorkspaceId: true,
    actions: [
      { name: 'search',       description: 'Recherche dans un index (params: indexName, query)' },
      { name: 'list_indexes', description: 'Liste tes indexes' },
      { name: 'browse',       description: 'Parcours un index (params: indexName, hitsPerPage)' },
    ],
  },
  sendgrid: {
    id: 'sendgrid', label: 'SendGrid (email transactionnel)', category: 'communication',
    description: 'Envoi mails transactionnels SendGrid (recus, OTP, alerts) — mieux que Gmail pour automation.',
    apiKeyLabel: 'API Key (SG.xxx)',
    apiKeyHelp: 'https://app.sendgrid.com/settings/api_keys — gratuit 100 mails/jour.',
    docUrl: 'https://docs.sendgrid.com/api-reference/mail-send/mail-send',
    actions: [
      { name: 'send', description: 'Envoie un mail (params: to, from, subject, content)' },
      { name: 'list_templates', description: 'Liste tes templates' },
    ],
  },
  // === IoT / SMART HOME ===
  mqtt: {
    id: 'mqtt', label: 'MQTT broker (publish/subscribe)', category: 'iot',
    description: 'Pub/sub vers un broker MQTT generique (Mosquitto, HiveMQ, AWS IoT, etc) via le bridge local (paho-mqtt).',
    apiKeyLabel: 'Username:Password (vide si broker anonyme)',
    apiKeyHelp: 'baseUrl = mqtt://host:1883 ou mqtts://host:8883. Format auth: <username>:<password> ou laisse vide.',
    docUrl: 'https://mqtt.org/',
    needsWorkspaceId: true,
    actions: [
      { name: 'publish',  description: 'Publish un message (params: topic, payload, qos?, retain?)' },
      { name: 'subscribe_once', description: 'Subscribe + recoit le 1er message (timeout 10s, params: topic)' },
    ],
  },
  tuya: {
    id: 'tuya', label: 'Tuya (smart plugs/bulbs)', category: 'iot',
    description: 'Smart Life / Tuya devices : prises, ampoules, thermostats compatibles Tuya Cloud.',
    apiKeyLabel: 'AccessKey:Secret',
    apiKeyHelp: 'https://iot.tuya.com/cloud/ -> projet -> AccessId+Secret. baseUrl region = https://openapi.tuyaeu.com (ou tuyaus/tuyacn).',
    docUrl: 'https://developer.tuya.com/en/docs/cloud/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_devices', description: 'Liste tes devices Tuya (params: uid)' },
      { name: 'device_status', description: 'Etat actuel (params: device_id)' },
      { name: 'send_command', description: 'Envoie un command (params: device_id, code, value) — destructif' },
    ],
  },
  tado: {
    id: 'tado', label: 'Tado (chauffage)', category: 'iot',
    description: 'Thermostats intelligents Tado : zones, temperatures, manual control.',
    apiKeyLabel: 'Bearer Token',
    apiKeyHelp: 'Tado utilise OAuth. Recupere un access_token via https://my.tado.com/oauth/token (grant=password, client_id=tado-web-app).',
    docUrl: 'https://shkspr.mobi/blog/2019/02/tado-api-guide-updated-for-2019/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_homes',     description: 'Tes maisons Tado' },
      { name: 'list_zones',     description: 'Zones d une maison (params: home_id)' },
      { name: 'zone_state',     description: 'Etat d une zone (params: home_id, zone_id)' },
      { name: 'set_temperature', description: 'Ajuste manuellement la temp (params: home_id, zone_id, temperature) — destructif' },
    ],
  },

  // === CI/CD ===
  circleci: {
    id: 'circleci', label: 'CircleCI (CI/CD)', category: 'dev',
    description: 'Pipelines, workflows, jobs CircleCI v2 API.',
    apiKeyLabel: 'Personal Token',
    apiKeyHelp: 'https://app.circleci.com/settings/user/tokens — cree un token personnel.',
    docUrl: 'https://circleci.com/docs/api/v2/',
    actions: [
      { name: 'list_projects',  description: 'Tes projets CircleCI suivis' },
      { name: 'list_pipelines', description: 'Pipelines recents (params: project_slug)' },
      { name: 'get_pipeline',   description: 'Details + workflows (params: pipeline_id)' },
      { name: 'list_jobs',      description: 'Jobs d un workflow (params: workflow_id)' },
      { name: 'rerun_workflow', description: 'Relance un workflow (params: workflow_id) — destructif' },
    ],
  },

  // === v14 : maison + cloud + fitness ===
  wyze: {
    id: 'wyze', label: 'Wyze (cams + plugs)', category: 'iot',
    description: 'Cameras + smart plugs Wyze via Wyze Web API (compte personnel).',
    apiKeyLabel: 'API Key + KeyId',
    apiKeyHelp: 'API Key Wyze : https://developer-api-console.wyze.com/ (apikey + keyid). baseUrl = https://api.wyzecam.com',
    docUrl: 'https://developer-api-console.wyze.com/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_devices', description: 'Liste tes cams + prises Wyze' },
      { name: 'snapshot',     description: 'Capture snapshot d une cam (param: device_mac)' },
      { name: 'turn_on_plug', description: 'Allume une prise Wyze' },
      { name: 'turn_off_plug',description: 'Eteint une prise Wyze' },
      { name: 'get_events',   description: 'Liste les events recents (mouvement, son)' },
    ],
  },
  nodered: {
    id: 'nodered', label: 'Node-RED (webhooks/flows)', category: 'iot',
    description: 'Auto-host Node-RED : declenche des flows via http-in webhook ou GET HTTP API admin.',
    apiKeyLabel: 'Auth Token (Bearer)',
    apiKeyHelp: 'Si Node-RED est protege par auth admin, utilise un token JWT. Sinon laisse vide. baseUrl = https://nodered.local:1880',
    docUrl: 'https://nodered.org/docs/',
    needsWorkspaceId: false,
    actions: [
      { name: 'trigger_webhook', description: 'POST /<endpoint> avec payload JSON — declenche un flow http-in' },
      { name: 'list_flows',      description: 'GET /flows — liste les flows (auth admin requis)' },
      { name: 'inject_message',  description: 'POST /inject/<id> — declenche un node inject' },
    ],
  },
  bambu: {
    id: 'bambu', label: 'Bambu Lab (3D printers)', category: 'iot',
    description: 'Imprimantes 3D Bambu Lab via Bambu Cloud API (X1, P1, A1 series).',
    apiKeyLabel: 'Bearer Token',
    apiKeyHelp: 'Login sur https://bambulab.com/ -> recupere le bearer du localStorage. baseUrl = https://api.bambulab.com',
    docUrl: 'https://bambulab.com/en/help-center',
    actions: [
      { name: 'list_printers', description: 'Liste tes imprimantes liees' },
      { name: 'get_printer_status', description: 'Statut + temperature + progress (param: dev_id)' },
      { name: 'list_jobs',     description: 'Jobs d impression recents' },
      { name: 'pause_print',   description: 'Met en pause un print en cours (destructif)' },
      { name: 'resume_print',  description: 'Reprend un print pause' },
      { name: 'cancel_print',  description: 'Annule un print en cours (destructif)' },
    ],
  },
  strava: {
    id: 'strava', label: 'Strava (fitness)', category: 'data',
    description: 'Fitness + activities Strava : courses, velo, marche, swim. Utilise un access_token OAuth2.',
    apiKeyLabel: 'Access Token (OAuth2)',
    apiKeyHelp: 'https://www.strava.com/settings/api -> "Your Access Token" (scope activity:read_all + profile:read_all).',
    docUrl: 'https://developers.strava.com/docs/reference/',
    actions: [
      { name: 'get_athlete', description: 'Profile athlete connecte' },
      { name: 'list_activities', description: 'Activites recentes (params: per_page, after)' },
      { name: 'get_activity', description: 'Details d une activite (param: id)' },
      { name: 'get_stats',    description: 'Stats globales de l athlete (totaux distance, temps)' },
      { name: 'list_segments', description: 'Segments starred par l athlete' },
    ],
  },

  // === v15 : project / dev / media ===
  trello: {
    id: 'trello', label: 'Trello (boards/cards)', category: 'productivity',
    description: 'Tableaux Trello : boards, listes, cards, checklists, due dates.',
    apiKeyLabel: 'Key:Token',
    apiKeyHelp: 'https://trello.com/app-key — recupere ta API Key + clique "Token". Format <KEY>:<TOKEN>.',
    docUrl: 'https://developer.atlassian.com/cloud/trello/rest/',
    actions: [
      { name: 'list_boards', description: 'Liste tes boards' },
      { name: 'list_lists',  description: 'Listes d un board (param: idBoard)' },
      { name: 'list_cards',  description: 'Cards d une liste (param: idList)' },
      { name: 'create_card', description: 'Cree une card (params: idList, name, desc, due)' },
      { name: 'move_card',   description: 'Deplace une card (params: idCard, idList)' },
      { name: 'archive_card',description: 'Archive une card (param: idCard)' },
    ],
  },
  jira: {
    id: 'jira', label: 'Jira Cloud (entreprise)', category: 'productivity',
    description: 'Jira Cloud : issues, projects, transitions, comments, JQL search.',
    apiKeyLabel: 'email:api_token',
    apiKeyHelp: 'https://id.atlassian.com/manage-profile/security/api-tokens — format <ton-email>:<TOKEN>. baseUrl = https://<workspace>.atlassian.net',
    docUrl: 'https://developer.atlassian.com/cloud/jira/platform/rest/v3/',
    needsWorkspaceId: false,
    actions: [
      { name: 'jql_search',     description: 'Recherche JQL (param: jql)' },
      { name: 'get_issue',      description: 'Details d une issue (param: key)' },
      { name: 'create_issue',   description: 'Cree une issue (params: projectKey, summary, issueType, description?)' },
      { name: 'add_comment',    description: 'Commente une issue (params: key, body)' },
      { name: 'transition_issue', description: 'Transite une issue (params: key, transitionId)' },
      { name: 'list_transitions', description: 'Transitions disponibles (param: key)' },
    ],
  },
  wakatime: {
    id: 'wakatime', label: 'WakaTime (dev time)', category: 'productivity',
    description: 'WakaTime : temps de code par editeur/projet/langage. Stats developpeur.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://wakatime.com/api-key',
    docUrl: 'https://wakatime.com/developers',
    actions: [
      { name: 'get_user',     description: 'Profile + total time' },
      { name: 'get_stats',    description: 'Stats global (param: range = last_7_days/last_30_days/last_year)' },
      { name: 'list_projects',description: 'Projets que tu code (les plus actifs)' },
      { name: 'get_project_stats', description: 'Stats d un projet (params: project, range)' },
      { name: 'list_summaries', description: 'Resume jour par jour (params: start, end)' },
    ],
  },
  plex: {
    id: 'plex', label: 'Plex Media Server', category: 'media',
    description: 'Plex : films, series, musique, sessions actives, scan bibliotheque.',
    apiKeyLabel: 'X-Plex-Token',
    apiKeyHelp: 'https://www.plex.tv/claim/ ou recupere depuis settings -> About -> Show advanced. baseUrl = http://<server>:32400',
    docUrl: 'https://github.com/Arcanemagus/plex-api/wiki',
    needsWorkspaceId: false,
    actions: [
      { name: 'list_libraries', description: 'Sections (Movies, Shows, Music)' },
      { name: 'search',         description: 'Recherche globale (param: q)' },
      { name: 'list_recently_added', description: 'Derniers ajouts (param: section)' },
      { name: 'list_sessions',  description: 'Sessions de lecture en cours' },
      { name: 'scan_section',   description: 'Force le scan d une section (param: section)' },
    ],
  },

  // === v16 monitoring + CRM ===
  grafana: {
    id: 'grafana', label: 'Grafana (monitoring)', category: 'data',
    description: 'Grafana : dashboards, alerts, query Prometheus/Loki/InfluxDB via datasource.',
    apiKeyLabel: 'API Key (Bearer)',
    apiKeyHelp: 'https://grafana.com/docs/grafana/latest/administration/api-keys/ — cree une key Editor/Viewer. baseUrl = https://<workspace>.grafana.net OU http://localhost:3000',
    docUrl: 'https://grafana.com/docs/grafana/latest/developers/http_api/',
    needsWorkspaceId: false,
    actions: [
      { name: 'list_dashboards', description: 'Liste les dashboards (param: query)' },
      { name: 'get_dashboard',   description: 'JSON d un dashboard (param: uid)' },
      { name: 'list_alerts',     description: 'Alerts en cours (firing/pending)' },
      { name: 'list_datasources',description: 'Datasources configurees' },
      { name: 'query_datasource',description: 'Query Prom/Loki/etc (params: datasource_uid, expr, range)' },
    ],
  },
  hubspot: {
    id: 'hubspot', label: 'HubSpot (CRM)', category: 'productivity',
    description: 'HubSpot CRM : contacts, deals, companies, notes, deals pipeline.',
    apiKeyLabel: 'Private App Token',
    apiKeyHelp: 'https://app.hubspot.com/private-apps/ -> Create app -> Token. Scopes: crm.objects.contacts.read|write, crm.objects.deals.*',
    docUrl: 'https://developers.hubspot.com/docs/api/crm',
    actions: [
      { name: 'list_contacts',  description: 'Contacts recents (param: limit)' },
      { name: 'get_contact',    description: 'Details d un contact (param: id)' },
      { name: 'create_contact', description: 'Cree un contact (params: email, firstname, lastname, phone)' },
      { name: 'list_deals',     description: 'Deals recents' },
      { name: 'create_deal',    description: 'Cree un deal (params: dealname, amount, dealstage)' },
      { name: 'add_note_to_contact', description: 'Ajoute une note a un contact (params: contactId, body)' },
    ],
  },

  // === v18 productivity / automation ===
  toggl: {
    id: 'toggl', label: 'Toggl Track (time tracking)', category: 'productivity',
    description: 'Toggl Track : timers, projets, rapports temps. Alternative simple a WakaTime pour le temps NON-CODE.',
    apiKeyLabel: 'API Token',
    apiKeyHelp: 'https://track.toggl.com/profile -> API Token (en bas de la page profil).',
    docUrl: 'https://engineering.toggl.com/docs/',
    actions: [
      { name: 'get_me',           description: 'Profile + workspaces' },
      { name: 'list_projects',    description: 'Projets d un workspace (param: workspace_id)' },
      { name: 'list_time_entries',description: 'Time entries recents (params: start_date, end_date YYYY-MM-DD)' },
      { name: 'start_timer',      description: 'Demarre un timer (params: workspace_id, project_id?, description)' },
      { name: 'stop_current_timer', description: 'Stoppe le timer en cours' },
      { name: 'get_current_timer',description: 'Timer actuellement actif' },
    ],
  },
  make_com: {
    id: 'make_com', label: 'Make.com (webhooks)', category: 'misc',
    description: 'Make.com (ex Integromat) : declenche un scenario via webhook URL. Universel pour automatisation cross-app.',
    apiKeyLabel: 'Webhook URL',
    apiKeyHelp: 'Cree un scenario sur https://eu.make.com/ avec un module Webhooks->Custom webhook et copie l URL. Format: https://hook.eu1.make.com/abc123...',
    docUrl: 'https://www.make.com/en/help/tools/webhooks',
    actions: [
      { name: 'trigger',  description: 'POST le payload sur le webhook (param: payload object)' },
      { name: 'trigger_get', description: 'GET avec query params (param: params object)' },
    ],
  },

  pinecone: {
    id: 'pinecone', label: 'Pinecone (vector DB)', category: 'ai',
    description: 'Vector DB managee pour RAG / similarity search. Indexe embeddings, query top-K.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://app.pinecone.io/ -> API Keys. baseUrl = host de ton index (ex: https://my-index-xxx.svc.us-east-1-aws.pinecone.io).',
    docUrl: 'https://docs.pinecone.io/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_indexes', description: 'Liste tes indexes Pinecone' },
      { name: 'describe_index_stats', description: 'Stats d un index (nb vectors, dimension)' },
      { name: 'query',        description: 'Top-K similarity search (params: vector, topK, filter?)' },
      { name: 'upsert',       description: 'Insert/update vectors (params: vectors[]) — destructif' },
      { name: 'delete',       description: 'Delete by id ou filter — destructif' },
    ],
  },
  mailchimp: {
    id: 'mailchimp', label: 'Mailchimp (newsletter)', category: 'communication',
    description: 'Mailing lists, campagnes, automations Mailchimp.',
    apiKeyLabel: 'API Key (xxx-us21)',
    apiKeyHelp: 'https://us1.admin.mailchimp.com/account/api/ — la cle finit par -us<N> (ton DC).',
    docUrl: 'https://mailchimp.com/developer/marketing/api/',
    actions: [
      { name: 'list_audiences', description: 'Liste des listes (audiences)' },
      { name: 'add_member',     description: 'Ajoute un email a une liste (destructif)' },
      { name: 'list_campaigns', description: 'Campagnes recentes' },
      { name: 'send_campaign',  description: 'Envoie une campagne (destructif)' },
    ],
  },
  auth0: {
    id: 'auth0', label: 'Auth0 (users/roles)', category: 'cloud',
    description: 'Gestion users + roles + organisations Auth0 via Management API.',
    apiKeyLabel: 'Management API Token',
    apiKeyHelp: 'https://manage.auth0.com/ -> Applications -> APIs -> Management API -> Test tab. baseUrl = https://<tenant>.auth0.com',
    docUrl: 'https://auth0.com/docs/api/management/v2',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_users',  description: 'Liste les users (params: q, page)' },
      { name: 'get_user',    description: 'Details d un user (params: id)' },
      { name: 'create_user', description: 'Cree un user (destructif)' },
      { name: 'list_roles',  description: 'Roles disponibles' },
    ],
  },
  clerk: {
    id: 'clerk', label: 'Clerk (auth alt)', category: 'cloud',
    description: 'Alternative Auth0 : gestion users/sessions/orgs via Clerk Backend API.',
    apiKeyLabel: 'Secret Key (sk_test_/sk_live_)',
    apiKeyHelp: 'https://dashboard.clerk.com/ -> Developers -> API Keys -> Secret keys.',
    docUrl: 'https://clerk.com/docs/reference/backend-api',
    actions: [
      { name: 'list_users',     description: 'Liste users (params: query, limit)' },
      { name: 'get_user',       description: 'Details user (params: id)' },
      { name: 'list_orgs',      description: 'Organisations' },
      { name: 'ban_user',       description: 'Ban un user (destructif)' },
    ],
  },
  cloudinary: {
    id: 'cloudinary', label: 'Cloudinary (images CDN)', category: 'cloud',
    description: 'CDN images + transformations on-the-fly (resize, crop, format).',
    apiKeyLabel: 'CloudName:ApiKey:ApiSecret',
    apiKeyHelp: 'https://cloudinary.com/console — copie CloudName + ApiKey + ApiSecret. Format <cloud>:<key>:<secret>.',
    docUrl: 'https://cloudinary.com/documentation/admin_api',
    actions: [
      { name: 'list_resources', description: 'Liste tes images (params: max_results)' },
      { name: 'usage',          description: 'Stats utilisation (storage, bandwidth)' },
      { name: 'transform_url',  description: 'Genere une URL CDN avec transformations (resize/crop/format)' },
    ],
  },
  sentry: {
    id: 'sentry', label: 'Sentry (errors)', category: 'cloud',
    description: 'Liste des issues/erreurs Sentry + commentaires + assignation.',
    apiKeyLabel: 'Auth Token',
    apiKeyHelp: 'https://sentry.io/settings/account/api/auth-tokens/ — scopes: project:read, event:read, issue:write.',
    docUrl: 'https://docs.sentry.io/api/',
    needsWorkspaceId: true,
    actions: [
      { name: 'list_projects', description: 'Liste les projets Sentry de ton org' },
      { name: 'list_issues',   description: 'Issues d un projet (params: org, project)' },
      { name: 'get_issue',     description: 'Details d une issue (params: issue_id)' },
      { name: 'resolve_issue', description: 'Marque une issue comme resolue (destructif)' },
    ],
  },

  // === RESEARCH ===
  perplexity: {
    id: 'perplexity', label: 'Perplexity AI (research)', category: 'ai',
    description: 'LLM avec recherche web temps reel + citations. Excellent pour les questions factuelles recentes.',
    apiKeyLabel: 'API Key (pplx-...)',
    apiKeyHelp: 'https://www.perplexity.ai/settings/api — pay-as-you-go.',
    docUrl: 'https://docs.perplexity.ai/api-reference/chat-completions',
    actions: [
      { name: 'chat',     description: 'Chat avec recherche web (params: messages, model?: "sonar"/"sonar-pro")' },
      { name: 'sonar',    description: 'Question factuelle avec citations (raccourci de chat)' },
    ],
  },

  // === APPLE — via Shortcuts webhook ===
  apple_reminders: {
    id: 'apple_reminders', label: 'Apple Reminders (Shortcuts)', category: 'productivity',
    description: 'Cree des rappels Apple natifs via un raccourci iOS/macOS qui poll le bridge.',
    apiKeyLabel: 'Webhook URL (depuis raccourci)',
    apiKeyHelp: 'Cree un raccourci iOS qui poll /api/cowork/mobile/poll, parse la cmd "create_reminder" et appele "Add new reminder" Shortcut. URL = ton tunnel cloudflared.',
    docUrl: 'https://support.apple.com/guide/shortcuts/welcome/ios',
    actions: [
      { name: 'create_reminder', description: 'Cree un rappel (params: title, notes?, due?, list?). Le tel doit poller.' },
      { name: 'list_reminders',  description: 'Demande au tel de retourner ses rappels (poll roundtrip)' },
    ],
  },

  // === 3D ===
  meshy: {
    id: 'meshy', label: 'Meshy AI (3D)', category: 'ai',
    description: 'Generation 3D haute qualite : text-to-3D, image-to-3D, text-to-texture.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://www.meshy.ai/api — gratuit 200 credits/mois.',
    docUrl: 'https://docs.meshy.ai/api',
    actions: [
      { name: 'me',                 description: 'Profil + credits restants (test connexion)' },
      { name: 'text_to_3d',         description: 'Genere un mesh 3D depuis un prompt texte' },
      { name: 'text_to_3d_status',  description: 'Statut d un job text_to_3d' },
      { name: 'image_to_3d',        description: 'Genere un mesh 3D depuis une image' },
      { name: 'text_to_texture',    description: 'Texture un mesh existant via prompt' },
    ],
  },

  // === LLM / AI ===
  openai: {
    id: 'openai', label: 'OpenAI', category: 'ai',
    description: 'GPT-* via OpenAI API.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://platform.openai.com/api-keys',
    docUrl: 'https://platform.openai.com/docs/api-reference',
    actions: [
      { name: 'chat', description: 'Chat completions' },
      { name: 'embed', description: 'Embeddings' },
    ],
  },
  anthropic: {
    id: 'anthropic', label: 'Anthropic Claude', category: 'ai',
    description: 'Claude via Anthropic API.',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://console.anthropic.com/settings/keys',
    docUrl: 'https://docs.anthropic.com/en/api',
    actions: [
      { name: 'chat', description: 'Messages API' },
    ],
  },
  mistral: {
    id: 'mistral', label: 'Mistral AI', category: 'ai',
    description: 'Mistral models (mistral-large, codestral, ...).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://console.mistral.ai/api-keys/',
    docUrl: 'https://docs.mistral.ai/api/',
    actions: [
      { name: 'chat', description: 'Chat completions' },
    ],
  },
  groq: {
    id: 'groq', label: 'Groq Cloud', category: 'ai',
    description: 'Inference ultra-rapide (Llama 3, Mixtral, etc.).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://console.groq.com/keys',
    docUrl: 'https://console.groq.com/docs',
    actions: [
      { name: 'chat', description: 'Chat completions' },
    ],
  },
  openrouter: {
    id: 'openrouter', label: 'OpenRouter', category: 'ai',
    description: 'Acces unifie a 100+ modeles (OpenAI/Anthropic/Mistral/...).',
    apiKeyLabel: 'API Key',
    apiKeyHelp: 'https://openrouter.ai/keys',
    docUrl: 'https://openrouter.ai/docs',
    actions: [
      { name: 'chat', description: 'Chat completions (params: model, messages)' },
      { name: 'list_models', description: 'Modeles disponibles' },
    ],
  },

  // === Machines (SSH/TCP) — Aurora prend controle d'un device ===
  machine_local: {
    id: 'machine_local', label: 'Machine: Localhost', category: 'iot',
    description: 'Execute commandes / scripts / installations sur cette machine (le PC qui fait tourner Aurora).',
    apiKeyLabel: 'n/a', apiKeyHelp: 'no auth needed', docUrl: '/HANDOFF_CODE_LOOP.md',
    actions: [
      { name: 'run', description: 'Execute une commande shell locale, retourne rc+stdout+stderr (params: command, timeout)' },
      { name: 'write_file', description: 'Ecrit un fichier dans un dossier choisi (params: path, content)' },
      { name: 'read_file', description: 'Lit un fichier local (params: path)' },
      { name: 'list_dir', description: 'Liste un dossier (params: path)' },
    ],
  },
  machine_pi: {
    id: 'machine_pi', label: 'Machine: Raspberry Pi', category: 'iot',
    description: 'Pilote un Raspberry Pi par SSH : GPIO, picamera2, deploiement de scripts, capture/analyse.',
    apiKeyLabel: 'SSH password ou cle', apiKeyHelp: 'configure le target via /api/connect/targets/save',
    docUrl: '/HANDOFF_CODE_LOOP.md',
    actions: [
      { name: 'probe', description: 'Verifie acces SSH + retourne info OS/python/node (params: target_name)' },
      { name: 'run', description: 'Execute commande shell sur le Pi (params: target_name, command, timeout)' },
      { name: 'upload', description: 'Upload un fichier sur le Pi (params: target_name, remote_path, content)' },
      { name: 'deploy_project', description: 'scp d un dossier de projet vers deploy_path/slug (params: target_name, files, slug)' },
      { name: 'gpio_blink', description: 'Helper haut niveau : pulse GPIO N (params: target_name, pin, count)' },
      { name: 'camera_snap', description: 'Helper picamera2 : capture image et la pull back (params: target_name, out_path)' },
    ],
  },
  machine_linux: {
    id: 'machine_linux', label: 'Machine: Serveur Linux (VPS/LAN)', category: 'iot',
    description: 'Serveur Linux generique (Ubuntu, Debian, Arch) accessible par SSH : deploiement web, services, base de donnees.',
    apiKeyLabel: 'SSH password ou cle', apiKeyHelp: 'configure le target via /api/connect/targets/save',
    docUrl: '/HANDOFF_CODE_LOOP.md',
    actions: [
      { name: 'probe', description: 'Verifie acces + uname/distro (params: target_name)' },
      { name: 'run', description: 'Execute commande (params: target_name, command, timeout)' },
      { name: 'upload', description: 'Upload fichier (params: target_name, remote_path, content)' },
      { name: 'deploy_project', description: 'Deploie un dossier projet (params: target_name, files, slug)' },
      { name: 'install_pkg', description: 'apt/yum/pacman install (params: target_name, package_name)' },
      { name: 'start_service', description: 'systemctl start <name> (params: target_name, service_name)' },
    ],
  },
  machine_ssh: {
    id: 'machine_ssh', label: 'Machine: SSH generique', category: 'iot',
    description: 'N\'importe quelle cible SSH (NAS, switch managed, BSD, Mac mini, etc.) — actions de bas niveau.',
    apiKeyLabel: 'SSH password ou cle', apiKeyHelp: 'configure le target via /api/connect/targets/save',
    docUrl: '/HANDOFF_CODE_LOOP.md',
    actions: [
      { name: 'probe', description: 'Test acces SSH (params: target_name OU host+user+port+password/key_path)' },
      { name: 'run', description: 'Execute commande (params: ..., command)' },
      { name: 'upload', description: 'Upload fichier (params: ..., remote_path, content)' },
      { name: 'tcp_probe', description: 'Test reachability TCP port (params: host, port)' },
      { name: 'keygen', description: 'Genere paire de cles ed25519 et retourne pubkey (params: comment)' },
    ],
  },

  // === Internal Aurora modules (cowork delegates to them) ===
  aurora_code: {
    id: 'aurora_code', label: 'Module: Code (codeOrchestrator interne)', category: 'dev',
    description: 'Génère, corrige, optimise du code via le pipeline Aurora interne (qwen3-coder + Vite/build + sandbox + fidelity gate).',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local', docUrl: '/HANDOFF_CODE_LOOP.md',
    actions: [
      { name: 'generate', description: 'Génère un projet complet à partir d\'un prompt (params: prompt, target?)' },
      { name: 'refactor', description: 'Refactorise du code existant (params: prompt, existing_files)' },
      { name: 'fix', description: 'Diagnostique et corrige un bug (params: prompt, error_log, files)' },
      { name: 'explain', description: 'Explique du code ligne par ligne (params: file_content)' },
    ],
  },
  aurora_3d: {
    id: 'aurora_3d', label: 'Module: 3D (Hunyuan3D pipeline interne)', category: 'media',
    description: 'Génère un mesh 3D PBR à partir d\'un prompt texte ou d\'une image (FLUX -> Hunyuan3D shape+paint -> HDRI render).',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local', docUrl: '/HANDOFF_HUNYUAN3D.md',
    actions: [
      { name: 'generate', description: 'Génère un mesh + textures + hero render à partir d\'un prompt (params: prompt, category?)' },
      { name: 'rebake', description: 'Reapplique color transfer Reinhard sur un GLB existant (params: glb_path, source_image)' },
      { name: 'animate', description: 'Apply animations (rotate/hover/emission/particles) à un GLB (params: glb_path, profile)' },
    ],
  },
  aurora_image: {
    id: 'aurora_image', label: 'Module: Image (FLUX/SDXL interne)', category: 'media',
    description: 'Génère une image depuis un prompt via FLUX.1-schnell ou SDXL-Turbo local.',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local',
    docUrl: 'https://huggingface.co/black-forest-labs/FLUX.1-schnell',
    actions: [
      { name: 'generate', description: 'text -> 1024x1024 PNG (params: prompt, model?, seed?)' },
      { name: 'img2img', description: 'Modifie une image existante (params: prompt, image_path, strength?)' },
      { name: 'enhance', description: 'Améliore saturation/contrast (params: image_path)' },
    ],
  },
  aurora_voice: {
    id: 'aurora_voice', label: 'Module: Voice (STT/TTS interne)', category: 'media',
    description: 'Synthèse vocale (TTS) + reconnaissance vocale (STT) via les services Aurora locaux.',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local',
    docUrl: '/AGENT_SYSTEM.md',
    actions: [
      { name: 'tts', description: 'Texte -> audio (params: text, voice?, lang?)' },
      { name: 'stt', description: 'Audio -> texte (params: audio_path)' },
      { name: 'idle_talking_head', description: 'Génère vidéo de portrait parlant en idle (params: duration)' },
    ],
  },
  aurora_video: {
    id: 'aurora_video', label: 'Module: Video (composition interne)', category: 'media',
    description: 'Compose une vidéo à partir d\'éléments (TTS + talking-head + scènes 3D + transitions).',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local',
    docUrl: '/AGENT_SYSTEM.md',
    actions: [
      { name: 'compose', description: 'Compose une vidéo finale (params: scenes[], voice_script, output_path)' },
      { name: 'talking_head', description: 'Vidéo lipsync à partir d\'un audio (params: audio_path, persona)' },
    ],
  },
  aurora_drawing: {
    id: 'aurora_drawing', label: 'Module: Drawing (sketch interpreter)', category: 'media',
    description: 'Interprète un croquis utilisateur et le transforme en visuel finalisé.',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local', docUrl: '/AGENT_SYSTEM.md',
    actions: [
      { name: 'interpret', description: 'sketch -> illustration polishée (params: sketch_path, style?)' },
    ],
  },
  aurora_learning: {
    id: 'aurora_learning', label: 'Module: Learning (academic)', category: 'productivity',
    description: 'Gère parcours scolaire, quiz BAC, ressources académiques.',
    apiKeyLabel: 'n/a', apiKeyHelp: 'module local', docUrl: '/AGENT_SYSTEM.md',
    actions: [
      { name: 'quiz', description: 'Génère un quiz adapté (params: topic, level, count)' },
      { name: 'lesson', description: 'Génère une fiche cours (params: topic, level, format)' },
      { name: 'bac_resource', description: 'Récupère une ressource BAC (params: filiere, matiere, year)' },
    ],
  },
}

// ---------------------------------------------------------------------------
// Semantic enrichment — each entry teaches the planner LLM WHEN/WHY to use
// this connector, what free tier exists, and what local fallback to use if
// the external service is unavailable / out of credits. Applied at module
// load to the CONNECTORS map below.
// ---------------------------------------------------------------------------

type SemanticOverride = Pick<ConnectorMeta, 'purpose' | 'whenToUse' | 'fallback' | 'freeTier'>

const SEMANTIC: Partial<Record<ConnectorId, SemanticOverride>> = {
  // === DEV / CLOUD ===
  github: { purpose: 'Hebergement de code source git, PRs, issues, CI Actions.', whenToUse: ['repo', 'depot', 'pull request', 'PR', 'issue', 'commit', 'release', 'github action', 'fork'], freeTier: 'gratuit pour repos publics + 2000 min Actions/mois' },
  gitlab: { purpose: 'Alternative GitHub : repos, MRs, CI GitLab.', whenToUse: ['gitlab', 'merge request', 'MR', 'pipeline gitlab'], freeTier: 'free tier genereux pour repos publics' },
  vercel: { purpose: 'Hebergement de sites/apps web (Next.js, React, etc.).', whenToUse: ['deploy vercel', 'preview deployment', 'production', 'next.js', 'edge function'], freeTier: 'Hobby plan gratuit (100GB bw/mois)' },
  netlify: { purpose: 'Alternative Vercel : sites statiques, edge functions.', whenToUse: ['netlify', 'jamstack', 'static site'], freeTier: 'Free plan 100GB bw/mois' },
  cloudflare: { purpose: 'DNS, Workers, Pages, R2 storage, CDN.', whenToUse: ['cloudflare', 'DNS', 'worker', 'CDN', 'R2', 'pages cf'], freeTier: 'free plan large + 100K requetes Workers/jour' },
  render: { purpose: 'Hebergement Web services + bases de donnees managees.', whenToUse: ['render.com', 'web service', 'background worker'], freeTier: 'free web service (s endort apres 15min inactivite)' },
  railway: { purpose: 'Hebergement apps + DB, deploy en 1 clic.', whenToUse: ['railway', 'deploy app', 'postgres managed'], freeTier: '5$ trial puis paiement' },
  fly: { purpose: 'Apps + machines globales (proche utilisateur).', whenToUse: ['fly.io', 'edge deploy', 'machine'], freeTier: 'pay-as-you-go, pas vraiment de free tier' },
  supabase: { purpose: 'Postgres + auth + storage + realtime managed.', whenToUse: ['supabase', 'postgres managed', 'auth users', 'realtime DB', 'row level security'], freeTier: 'Free 500MB DB + 1GB storage' },

  // === PRODUCTIVITY ===
  notion: { purpose: 'Base de connaissances + wiki + DB Notion.', whenToUse: ['notion', 'wiki', 'database notion', 'page notion', 'workspace notion'], freeTier: 'Personal free' },
  linear: { purpose: 'Issue tracking ergonomique pour equipes produit.', whenToUse: ['linear', 'issue produit', 'sprint', 'roadmap'], freeTier: 'Free plan 250 issues' },
  asana: { purpose: 'Gestion de taches + projets cross-equipes.', whenToUse: ['asana', 'task', 'projet equipe'], freeTier: 'Free 15 personnes' },
  todoist: { purpose: 'To-do list personnelle + recurring tasks.', whenToUse: ['todoist', 'todo', 'rappel quotidien', 'recurring'], freeTier: 'Free 5 projets' },

  // === COMMUNICATION ===
  slack: { purpose: 'Messages dans channels Slack via bot.', whenToUse: ['slack', 'channel', 'team chat', 'notif slack'], freeTier: 'Free 90 jours d historique' },
  discord: { purpose: 'Bot Discord : envoi messages, lecture serveurs.', whenToUse: ['discord', 'serveur discord', 'channel discord', 'bot discord'], freeTier: 'gratuit (limites bot)' },
  telegram: { purpose: 'Bot Telegram (notifications mobiles, groupes).', whenToUse: ['telegram', 'bot telegram', 'notif phone', 'group chat'], freeTier: 'gratuit illimite' },

  // === CALENDAR/MAIL ===
  gcal: { purpose: 'Lecture + creation d evenements Google Calendar.', whenToUse: ['agenda', 'rendez-vous', 'evenement', 'reunion', 'planning', 'calendar'], freeTier: 'gratuit (compte Google)' },
  gmail: { purpose: 'Lecture + envoi de mails depuis Gmail.', whenToUse: ['mail', 'email', 'gmail', 'envoyer un mail', 'inbox'], freeTier: 'gratuit (compte Google)' },

  // === STORAGE ===
  gdrive: { purpose: 'Lecture/upload de fichiers Google Drive.', whenToUse: ['google drive', 'gdrive', 'fichier cloud', 'upload drive'], freeTier: '15 GB gratuit' },
  dropbox: { purpose: 'Lecture/upload Dropbox.', whenToUse: ['dropbox', 'fichier cloud'], freeTier: '2 GB gratuit' },

  // === MEDIA ===
  spotify: { purpose: 'Controle Spotify : recherche, play/pause/next, et Spotify Connect (changer d enceinte/PC/tel).', whenToUse: ['musique', 'spotify', 'play', 'pause', 'chanson', 'playlist', 'morceau', 'enceinte', 'sonos', 'change appareil'], freeTier: 'free Spotify (publicites)' },
  youtube: { purpose: 'Recherche videos + stats YouTube.', whenToUse: ['youtube', 'video', 'cherche une video', 'tuto'], freeTier: 'API gratuite : 10K units/jour (~100 search)' },

  // === IoT ===
  home_assistant: { purpose: 'Domotique : lumieres, capteurs, scenes, climatisation.', whenToUse: ['lumiere', 'volet', 'thermostat', 'capteur', 'scene', 'domotique', 'maison', 'allume', 'eteint'], freeTier: 'gratuit (self-host)' },
  philips_hue: { purpose: 'Lumieres Hue via le bridge local (alt. Home Assistant).', whenToUse: ['hue', 'lumiere philips', 'ambiance lumineuse'], freeTier: 'gratuit (hardware)' },

  // === DATA ===
  openweather: { purpose: 'Meteo actuelle + previsions par ville/coords.', whenToUse: ['meteo', 'temps qu il fait', 'temperature', 'pluie', 'previsions'], freeTier: 'free 1000 calls/jour' },
  translate_deepl: { purpose: 'Traduction qualite premium (meilleure que Google).', whenToUse: ['traduire', 'traduction', 'translate', 'EN -> FR', 'multilingue'], freeTier: 'free 500K chars/mois', fallback: { kind: 'local-llm', target: 'mainModel', note: 'A defaut DeepL, utilise mainModel Ollama avec un prompt "Traduit ceci :"' } },
  maps_google: { purpose: 'Geocoding + itineraires Google Maps.', whenToUse: ['itineraire', 'route', 'directions', 'geocode', 'adresse', 'comment aller'], freeTier: '$200 credit/mois (~28K geocodes)' },
  wikipedia: { purpose: 'Recherche encyclopedique + extraits Wikipedia.', whenToUse: ['wikipedia', 'wiki', 'definition', 'qu est-ce que', 'qui est', 'histoire de'], freeTier: 'public, illimite' },
  arxiv: { purpose: 'Recherche papiers de recherche scientifiques.', whenToUse: ['paper', 'recherche', 'arxiv', 'publication', 'these', 'science'], freeTier: 'public, illimite' },
  hackernews: { purpose: 'Actualites tech + recherche HN.', whenToUse: ['hacker news', 'HN', 'actu tech', 'startup news'], freeTier: 'public, illimite' },
  reddit: { purpose: 'Lecture des posts Reddit (read-only).', whenToUse: ['reddit', 'subreddit', 'r/', 'avis communaute'], freeTier: 'public read-only, illimite' },

  // === AI ===
  huggingface: { purpose: 'Recherche modeles HF + Inference API hosted.', whenToUse: ['hugging face', 'modele HF', 'inference API', 'embeddings HF'], freeTier: '~30K req/mois sur Inference API hostee', fallback: { kind: 'local-llm', target: 'ollama', note: 'A defaut HF, utilise ollama local pour la generation/embedding' } },
  replicate: { purpose: 'Predictions Replicate : image gen, video gen, etc.', whenToUse: ['replicate', 'flux replicate', 'video gen'], freeTier: 'free trial limite ~$0.50', fallback: { kind: 'local-module', target: 'image', note: 'Pour images, retombe sur ComfyUI/FLUX local (module image)' } },
  stable_horde: { purpose: 'Generation d images crowd-sourced gratuite.', whenToUse: ['stable horde', 'image gratuite'], freeTier: 'gratuit (kudos), file d attente possible', fallback: { kind: 'local-module', target: 'image', note: 'A defaut, utilise ComfyUI local (instant, sans file d attente)' } },
  meshy: { purpose: 'Generation 3D haute qualite (text-to-3D, image-to-3D, text-to-texture). Quand active = qualite top; sinon retombe sur Hunyuan3D/DreamGaussian local.', whenToUse: ['3D', 'mesh', 'modele 3D', 'figurine', 'objet 3D', 'avatar 3D', 'texture mesh'], freeTier: '200 credits/mois gratuit', fallback: { kind: 'local-module', target: 'three-d', note: 'A defaut Meshy (credits epuises), retombe sur le module 3D local : Hunyuan3D (defaut) / DreamGaussian (stylise) / Blender (mecanique). Qualite OK, pas premium.' } },
  brave_search: { purpose: 'Recherche web sans tracking (alternative Google).', whenToUse: ['recherche web', 'google', 'cherche sur internet', 'find online'], freeTier: 'free 2000 req/mois' },

  // === DESIGN ===
  canva: { purpose: 'Lecture/export de designs Canva.', whenToUse: ['canva', 'flyer', 'poster', 'social media post', 'design canva'], freeTier: 'depend du plan Canva utilisateur' },
  figma: { purpose: 'Lecture de fichiers Figma + commentaires.', whenToUse: ['figma', 'design ui', 'mockup', 'wireframe figma'], freeTier: 'free tier 3 fichiers' },

  // === COMMERCE ===
  stripe: { purpose: 'Customers, charges, subscriptions Stripe.', whenToUse: ['stripe', 'paiement', 'abonnement', 'customer stripe', 'charge', 'mrr'], freeTier: 'pay-per-transaction (1.4%+0.25 EU)' },

  // === INFRA / DATA ===
  postgres: { purpose: 'Execute du SQL sur ta base PostgreSQL via le bridge local.', whenToUse: ['sql', 'select', 'requete db', 'postgres', 'pg', 'analyse table'], freeTier: 'gratuit (self-host) — DSN reste local' },
  redis_upstash: { purpose: 'Redis cache + counters via REST.', whenToUse: ['redis', 'cache', 'counter', 'session store', 'pubsub'], freeTier: 'free 10K commands/jour, 256MB' },
  s3: { purpose: 'Stockage objet compatible S3 (AWS, MinIO local, R2, B2).', whenToUse: ['s3', 'bucket', 'objet stocke', 'upload fichier', 'minio', 'r2', 'backblaze'], freeTier: 'depend du provider (R2 = 10GB gratuit/mois)' },
  tailscale: { purpose: 'Liste/admin tes machines Tailscale (VPN mesh).', whenToUse: ['tailscale', 'vpn', 'mes machines', 'tailnet', 'liste devices'], freeTier: 'free 100 devices personal' },
  plausible: { purpose: 'Analytics web respectueuse vie privee (sans cookies).', whenToUse: ['plausible', 'analytics', 'visiteurs', 'pageviews', 'sources de trafic', 'bounce'], freeTier: '30 jours trial puis paiement' },
  pushover: { purpose: 'Notifications push instantanees vers tes appareils.', whenToUse: ['notification', 'push', 'pushover', 'rappel mobile', 'alerte'], freeTier: '$5 lifetime par plateforme' },
  twilio: { purpose: 'Envoi SMS/WhatsApp/appels vocaux via Twilio. Quand tu veux contacter un humain par tel.', whenToUse: ['sms', 'envoie un message', 'whatsapp', 'appelle', 'twilio', 'phone'], freeTier: 'trial $15 credit' },
  openstreetmap: { purpose: 'Geocoding gratuit OSM (alternative Google Maps libre).', whenToUse: ['adresse', 'coordonnees gps', 'geocode', 'nominatim', 'osm'], freeTier: 'public, fair-use 1req/s', fallback: { kind: 'connector', target: 'maps_google', note: 'Si OSM rate-limit, retombe sur Google Maps si configure.' } },

  // === CYBER / OSINT ===
  hibp: { purpose: 'Verifier si un email/password est compromis dans une fuite.', whenToUse: ['hibp', 'fuite', 'pwned', 'leak', 'compromis', 'mot de passe leak', 'email leak'], freeTier: 'pay 3.50$/mois (sauf pwned_password public via k-anonymity)' },
  abuseipdb: { purpose: 'Reputation IP : detecter scanners, brute-force, abusers.', whenToUse: ['abuseipdb', 'reputation ip', 'mauvaise ip', 'scanner detection', 'cyber threat'], freeTier: '1000 req/jour gratuit' },

  // === CULTURE / LOISIRS ===
  discogs: { purpose: 'Catalogue musique vinyles/CDs : recherche, prix, releases.', whenToUse: ['discogs', 'vinyle', 'cd', 'album musique', 'cherche un album', 'discographie'], freeTier: 'gratuit (token personnel illimite)' },
  igdb: { purpose: 'Base IGDB des jeux video (cherche, scores, plateformes).', whenToUse: ['jeu', 'jeu video', 'game', 'igdb', 'console', 'rating jeu', 'sortie'], freeTier: '4 req/sec gratuit via Twitch OAuth' },
  openlibrary: { purpose: 'Recherche de livres + ebooks gratuits Open Library.', whenToUse: ['livre', 'book', 'auteur', 'isbn', 'bibliotheque', 'ebook', 'openlibrary'], freeTier: 'public, illimite' },

  // === APPLE ===
  apple_reminders: { purpose: 'Cree des rappels Apple natifs via raccourci iOS qui poll le bridge.', whenToUse: ['rappel', 'reminder', 'note moi', 'apple reminder', 'iphone reminder', 'ios reminder'], freeTier: 'gratuit (necessite iOS Shortcuts importe)' },

  // === IMAGE / MAPS / FINANCE / RESEARCH ===
  stability_ai: { purpose: 'Generation d images Stable Diffusion 3 / Ultra haute qualite.', whenToUse: ['image', 'sd3', 'stable diffusion', 'genere image', 'visuel premium'], freeTier: '25 credits gratuits inscription, puis pay', fallback: { kind: 'local-module', target: 'image', note: 'A defaut Stability AI, retombe sur ComfyUI/FLUX local (gratuit illimite).' } },
  mapbox: { purpose: 'Maps premium : geocoding/directions/tiles. Plus rapide qu OSM, plus complet.', whenToUse: ['mapbox', 'itineraire', 'directions', 'geocode rapide', 'tile vectorielle'], freeTier: 'free 50K req/mois', fallback: { kind: 'connector', target: 'openstreetmap', note: 'Si Mapbox quota epuise, retombe sur OSM Nominatim (lent mais public).' } },
  coingecko: { purpose: 'Prix crypto temps reel + historiques (BTC, ETH, alt-coins).', whenToUse: ['crypto', 'bitcoin', 'btc', 'eth', 'prix coin', 'cours crypto', 'altcoin'], freeTier: 'public 10-30 req/min sans cle' },
  polygon: { purpose: 'Donnees marche US : actions, options, forex, crypto avec historique.', whenToUse: ['action', 'stock', 'apple inc', 'tsla', 'cours bourse', 'forex', 'usd eur', 'sp500'], freeTier: 'free 5 req/min' },
  perplexity: { purpose: 'LLM avec recherche web temps reel + citations sources. Pour questions factuelles recentes.', whenToUse: ['perplexity', 'cherche sur le web', 'actualite', 'recent', 'recherche avec citations', 'factuel'], freeTier: 'pay-per-token', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si Perplexity epuise, retombe sur mainModel local (sans recherche web).' } },

  // === OBSERVABILITY ===
  datadog: { purpose: 'Metriques + logs + monitors Datadog (cloud observabilite).', whenToUse: ['datadog', 'metrics', 'logs prod', 'monitor cpu', 'apm', 'sli/slo', 'alertes prod'], freeTier: '14-day trial puis paiement' },
  sentry: { purpose: 'Tracking erreurs application : exceptions Python/JS/etc + stack traces.', whenToUse: ['sentry', 'erreur prod', 'exception', 'stack trace', 'crash report', 'bug user'], freeTier: 'free 5K errors/mois' },

  // === GAMIFICATION / SEARCH / EMAIL / CDN ===
  habitica: { purpose: 'Gamification de tes habitudes/taches : RPG avec niveau/gold/monstres.', whenToUse: ['habitica', 'habitude', 'gamification', 'niveau', 'rpg todo', 'recompense'], freeTier: 'gratuit (premium optionnel)' },
  algolia: { purpose: 'Recherche SaaS instantanee pour ton site/app (indexer + searcher).', whenToUse: ['algolia', 'recherche site', 'search engine', 'index', 'instant search', 'facets'], freeTier: '10K records + 10K req/mois free' },
  sendgrid: { purpose: 'Email transactionnel (OTP, recus, alerts). Plus fiable que Gmail pour automation.', whenToUse: ['sendgrid', 'email transactionnel', 'envoie mail auto', 'OTP', 'newsletter'], freeTier: '100 mails/jour gratuit' },
  cloudinary: { purpose: 'CDN images + transformations on-the-fly (resize/crop/format/quality).', whenToUse: ['cloudinary', 'image cdn', 'thumbnail', 'redimensionner image', 'optimisation image'], freeTier: '25 GB storage + 25 GB bw gratuit' },

  // === VECTOR DB / NEWSLETTER / AUTH ===
  pinecone: { purpose: 'Vector DB pour RAG (retrieval-augmented generation) : indexe embeddings, recherche similarite top-K.', whenToUse: ['pinecone', 'rag', 'vector', 'embedding search', 'similarity', 'semantic search'], freeTier: 'free 1 index + 100K vectors gratuit' },
  mailchimp: { purpose: 'Mailing lists + campagnes newsletter Mailchimp.', whenToUse: ['mailchimp', 'newsletter', 'mailing list', 'campagne email', 'subscribers'], freeTier: 'free 500 contacts + 1K mails/mois' },
  auth0: { purpose: 'Gestion users + roles + organisations Auth0 (Management API).', whenToUse: ['auth0', 'users gestion', 'roles', 'identity', 'sso users', 'liste utilisateurs'], freeTier: 'free 7K active users/mois' },
  clerk: { purpose: 'Alternative moderne Auth0 : users/sessions/orgs via API simple.', whenToUse: ['clerk', 'auth users', 'session', 'organisations', 'identity gestion'], freeTier: 'free 10K MAU' },

  // === IoT ===
  mqtt: { purpose: 'Pub/sub MQTT generique (Mosquitto, HiveMQ, AWS IoT, ...).', whenToUse: ['mqtt', 'pub/sub', 'capteurs', 'iot generique', 'broker'], freeTier: 'gratuit (self-host Mosquitto)' },
  tuya: { purpose: 'Smart Life / Tuya : prises connectees, ampoules, thermostats compatibles Tuya.', whenToUse: ['tuya', 'smart plug', 'smart life', 'prise connectee', 'ampoule connectee'], freeTier: 'gratuit (Tuya Cloud)' },
  tado: { purpose: 'Thermostats intelligents Tado.', whenToUse: ['tado', 'chauffage', 'thermostat smart', 'temperature maison'], freeTier: 'gratuit (compte Tado)' },
  // v14
  wyze: { purpose: 'Cameras + smart plugs Wyze — surveillance domestique abordable.', whenToUse: ['wyze', 'camera', 'cam wyze', 'snapshot', 'surveillance', 'smart plug wyze', 'evt mouvement'], freeTier: 'API gratuit pour usage perso' },
  nodered: { purpose: 'Auto-host Node-RED : declenche des flows via webhooks ou API admin.', whenToUse: ['nodered', 'node-red', 'flow', 'webhook trigger', 'automation perso', 'iot dashboard'], freeTier: 'gratuit (self-host)' },
  bambu: { purpose: 'Imprimantes 3D Bambu Lab : statut + jobs + pause/resume/cancel print.', whenToUse: ['bambu', 'bambu lab', 'imprimante 3d', 'print 3d', '3d printer', 'pause print', 'resume print'], freeTier: 'gratuit (compte Bambu)' },

  // === CI/CD ===
  circleci: { purpose: 'CircleCI : pipelines + workflows + jobs CI/CD.', whenToUse: ['circleci', 'ci/cd', 'pipeline', 'build status', 'rerun workflow'], freeTier: 'free 6K min/mois' },

  // === Fitness / health (v14) ===
  strava: { purpose: 'Strava : activites sportives (run, velo, marche, swim) + stats annuelles.', whenToUse: ['strava', 'fitness', 'course', 'run', 'velo', 'cyclisme', 'sport', 'distance parcourue', 'stats sport'], freeTier: 'API gratuit (rate-limit 100 req/15min, 1000/jour)' },

  // === v15 productivity / project / dev / media ===
  trello: { purpose: 'Trello : tableaux kanban, cards, checklists, deadlines.', whenToUse: ['trello', 'kanban', 'board', 'card', 'liste taches', 'todo board'], freeTier: 'free 10 boards par workspace' },
  jira: { purpose: 'Jira Cloud : issues entreprise, JQL, transitions, sprints.', whenToUse: ['jira', 'issue entreprise', 'JQL', 'sprint jira', 'epic', 'subtask', 'bug ticket'], freeTier: 'free pour <10 users' },
  wakatime: { purpose: 'WakaTime : suivi du temps de code par projet/langage/editeur.', whenToUse: ['wakatime', 'temps code', 'time tracking dev', 'productivite dev', 'stats coding'], freeTier: 'free 14 jours d historique' },
  plex: { purpose: 'Plex Media Server : films, series, musique, sessions actives.', whenToUse: ['plex', 'film', 'serie', 'media server', 'que regarder', 'sessions plex', 'bibliotheque'], freeTier: 'gratuit (self-host)' },

  // === v16 monitoring + CRM ===
  grafana: { purpose: 'Grafana : dashboards, alerts, query datasources (Prometheus/Loki/InfluxDB).', whenToUse: ['grafana', 'dashboard', 'alerte', 'monitoring', 'metriques', 'graphana', 'prometheus query'], freeTier: 'free Cloud + self-host gratuit' },
  hubspot: { purpose: 'HubSpot CRM : contacts, deals, pipelines, notes.', whenToUse: ['hubspot', 'crm', 'contact', 'deal', 'sales pipeline', 'lead', 'note client'], freeTier: 'free CRM 1M contacts' },

  // === v18 productivity / automation ===
  toggl: { purpose: 'Toggl Track : timers + rapports temps NON-CODE (reunions, taches admin, projets clients).', whenToUse: ['toggl', 'time tracking client', 'timer', 'reunion', 'temps facture', 'admin time'], freeTier: 'free 5 users + projets illimites' },
  make_com: { purpose: 'Make.com (Integromat) : webhook universel pour declencher tout scenario d automatisation cross-app.', whenToUse: ['make.com', 'integromat', 'webhook automation', 'declenche scenario', 'automation workflow'], freeTier: 'free 1000 ops/mois' },

  // === LLM ===
  // Important : ces LLM externes sont des FALLBACKS HAUT DE GAMME pour quand
  // mainModel local ne suffit pas. Ils retombent sur ollama si quota epuise.
  openai: { purpose: 'GPT-* (OpenAI) — quand tu veux la qualite GPT-4o ou un avis externe.', whenToUse: ['gpt', 'openai', 'avis externe', 'comparer', 'meilleur que mon llama'], freeTier: 'pay-per-token (pas de free)', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si OpenAI epuise/payant, utilise mainModel Ollama (llama4:scout) localement.' } },
  anthropic: { purpose: 'Claude (Anthropic) — raisonnement de pointe (claude-sonnet-4-6, opus).', whenToUse: ['claude', 'anthropic', 'raisonnement complexe', 'maths', 'code review pousse', 'opus', 'sonnet'], freeTier: 'pay-per-token + workbench gratuit limite', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si Anthropic epuise, utilise mainModel local (llama4:scout) — moins fort en raisonnement mais OK pour la majorite des cas.' } },
  mistral: { purpose: 'Mistral large + Codestral — qualite EU premium.', whenToUse: ['mistral', 'codestral', 'EU LLM', 'francais natif'], freeTier: 'free tier limite', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si Mistral epuise, retombe sur mainModel local.' } },
  groq: { purpose: 'Inference ultra-rapide (Llama/Mixtral) — quand la latence compte.', whenToUse: ['groq', 'rapide', 'realtime', 'latency', 'instant'], freeTier: 'free tier 30 req/min', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si Groq epuise, retombe sur mainModel local (plus lent mais aucune limite).' } },
  openrouter: { purpose: 'Acces unifie a 100+ modeles (un seul token, GPT/Claude/Mistral/Gemini/...).', whenToUse: ['openrouter', 'multi-llm', 'gemini', 'comparer modeles', 'bench llm'], freeTier: 'pay-per-token, certains modeles free', fallback: { kind: 'local-llm', target: 'mainModel', note: 'Si OpenRouter epuise, retombe sur mainModel local.' } },

  // === Machines ===
  machine_local: {
    purpose: 'PC local d Aurora : execute shell, ecrit/lit fichiers, installe paquets, lance scripts.',
    whenToUse: ['mon pc', 'localement', 'sur ce pc', 'cmd', 'powershell', 'shell local', 'installer dependance', 'creer fichier local', 'lister dossier'],
    freeTier: 'gratuit (machine du user)',
  },
  machine_pi: {
    purpose: 'Raspberry Pi du user (sur le LAN) : pilote GPIO, camera, capteurs, deploie code Python, ouvre serveur web local.',
    whenToUse: ['pi', 'raspberry', 'gpio', 'led', 'picamera', 'capteur', 'cible pi', 'mon raspberry', 'sur le pi', 'IoT pi'],
    freeTier: 'gratuit (device du user)',
  },
  machine_linux: {
    purpose: 'Serveur Linux du user (VPS, LAN) : deploie web, installe paquets apt/yum, configure systemd, push projet via scp.',
    whenToUse: ['vps', 'serveur', 'mon serveur', 'mon vps', 'mon nas', 'ubuntu', 'debian', 'machine linux', 'deploiement remote', 'systemctl'],
    freeTier: 'gratuit (machine du user)',
  },
  machine_ssh: {
    purpose: 'Cible SSH generique (mac mini, BSD, switch, NAS) : bas niveau run/upload/tcp_probe/keygen.',
    whenToUse: ['ssh generique', 'ma machine', 'mon mac', 'NAS', 'switch', 'BSD', 'connexion ssh'],
    freeTier: 'gratuit',
  },

  // === Internal Aurora modules ===
  aurora_code: {
    purpose: 'Module Code interne : génération/refactor/fix/explication via qwen3-coder + Vite build + sandbox. Préfere ça à la génération inline pour tout besoin de code complet.',
    whenToUse: ['ecris du code', 'genere une page', 'genere une app', 'refactor', 'fix bug', 'corrige', 'expliquer code', 'crée projet', 'site web', 'react vite', 'three.js scene', 'cli python', 'rest api', 'jeu canvas'],
    freeTier: 'gratuit (Ollama local)',
  },
  aurora_3d: {
    purpose: 'Module 3D interne : génère mesh PBR (Hunyuan3D shape+paint), animations procédurales, render HDRI Cycles. Utiliser pour toute demande de "modèle 3D", "asset", "mesh", "scène 3D".',
    whenToUse: ['modele 3d', 'mesh', '3d asset', 'glb', 'mtl', 'three.js mesh', 'object 3d', 'scene 3d', 'pbr', 'hunyuan'],
    freeTier: 'gratuit (modèles locaux)',
  },
  aurora_image: {
    purpose: 'Module Image interne : génération d\'images via FLUX.1-schnell ou SDXL-Turbo local. Utiliser pour visuel 2D, illustrations, hero shots, références.',
    whenToUse: ['image', 'illustration', 'logo', 'hero shot', 'visuel', 'photo style', 'flux', 'sdxl', 'render'],
    freeTier: 'gratuit (modèles locaux)',
  },
  aurora_voice: {
    purpose: 'Module Voice interne : TTS (synthèse vocale) + STT (reconnaissance). Indispensable pour générer voix-off ou comprendre un audio user.',
    whenToUse: ['voix', 'tts', 'stt', 'audio', 'parler', 'transcription', 'lipsync', 'voix off'],
    freeTier: 'gratuit',
  },
  aurora_video: {
    purpose: 'Module Video interne : composition de vidéos (talking-head + scènes + transitions). Pour leçon vidéo, présentation animée, démo.',
    whenToUse: ['video', 'film', 'animation', 'presentation', 'talking head', 'demo video'],
    freeTier: 'gratuit',
  },
  aurora_drawing: {
    purpose: 'Module Drawing interne : transforme un croquis utilisateur en illustration finalisée.',
    whenToUse: ['dessin', 'croquis', 'sketch', 'illustration', 'esquisse'],
    freeTier: 'gratuit',
  },
  aurora_learning: {
    purpose: 'Module Learning interne : quiz BAC, fiches cours, ressources académiques adaptées à la filière de l\'utilisateur.',
    whenToUse: ['quiz', 'cours', 'lecon', 'bac', 'reviser', 'fiche', 'academique', 'STI2D', 'SIN'],
    freeTier: 'gratuit',
  },
}

// Apply semantics
for (const id of Object.keys(SEMANTIC) as ConnectorId[]) {
  const c = CONNECTORS[id]
  const s = SEMANTIC[id]
  if (c && s) Object.assign(c, s)
}

// ---------------------------------------------------------------------------
// Helpers exported pour le planner — produire un brief textuel des
// connecteurs ACTIVES pour que le LLM sache quand les utiliser et quand
// retomber sur un fallback local.
// ---------------------------------------------------------------------------

export function buildConnectorBriefForLLM(
  enabled: Array<{ id: ConnectorId; quotaExhausted: boolean }>,
): string {
  if (enabled.length === 0) return ''
  const lines: string[] = []
  for (const { id, quotaExhausted } of enabled) {
    const meta = CONNECTORS[id]
    if (!meta) continue
    let line = `- ${meta.label} (id=${id})`
    if (meta.purpose) line += ` — ${meta.purpose}`
    if (meta.whenToUse?.length) line += ` (mots-cles: ${meta.whenToUse.slice(0, 6).join(', ')})`
    if (quotaExhausted && meta.fallback) {
      line += `\n  ⚠ QUOTA EPUISE — ${meta.fallback.note}`
    } else if (meta.freeTier) {
      line += `\n  free tier: ${meta.freeTier}`
    }
    lines.push(line)
  }
  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Test connectors (cheap auth check)
// ---------------------------------------------------------------------------

export async function testConnector(
  id: ConnectorId,
  config: { apiKey?: string; baseUrl?: string; workspaceId?: string },
): Promise<ConnectorTestResult> {
  const key = (config.apiKey || '').trim()
  if (!key) return { ok: false, message: 'API key vide' }

  // Public APIs without keys: skip the test
  if (['wikipedia', 'arxiv', 'hackernews', 'reddit', 'openstreetmap', 'openlibrary', 'coingecko'].includes(id)) {
    return { ok: true, message: 'public API — pas de cle requise' }
  }

  try {
    switch (id) {
      case 'github':         return await testGitHub(key)
      case 'gitlab':         return await testGitLab(key)
      case 'vercel':         return await testVercel(key, config.workspaceId)
      case 'netlify':        return await testNetlify(key)
      case 'cloudflare':     return await testCloudflare(key, config.workspaceId)
      case 'render':         return await testRender(key)
      case 'railway':        return await testRailway(key)
      case 'fly':            return await testFly(key)
      case 'supabase':       return await testSupabase(key, config.baseUrl)
      case 'notion':         return await testNotion(key)
      case 'linear':         return await testLinear(key)
      case 'asana':          return await testAsana(key)
      case 'todoist':        return await testTodoist(key)
      case 'slack':          return await testSlack(key)
      case 'discord':        return await testDiscord(key)
      case 'telegram':       return await testTelegram(key)
      case 'gcal':           return await testGoogleCalendar(key)
      case 'gmail':          return await testGmail(key)
      case 'gdrive':         return await testGoogleDrive(key)
      case 'dropbox':        return await testDropbox(key)
      case 'spotify':        return await testSpotify(key)
      case 'youtube':        return await testYouTube(key)
      case 'home_assistant': return await testHomeAssistant(key, config.workspaceId)
      case 'philips_hue':    return await testHue(key, config.workspaceId)
      case 'openweather':    return await testOpenWeather(key)
      case 'translate_deepl':return await testDeepL(key)
      case 'maps_google':    return await testMaps(key)
      case 'huggingface':    return await testHF(key)
      case 'replicate':      return await testReplicate(key)
      case 'stable_horde':   return await testHorde(key)
      case 'meshy':          return await testMeshy(key)
      case 'brave_search':   return await testBrave(key)
      case 'canva':          return await testCanva(key)
      case 'figma':          return await testFigma(key)
      case 'stripe':         return await testStripe(key)
      case 'openai':         return await testOpenAI(key)
      case 'anthropic':      return await testAnthropic(key)
      case 'mistral':        return await testMistral(key)
      case 'groq':           return await testGroq(key)
      case 'openrouter':     return await testOpenRouter(key)
      case 'postgres':       return await testPostgres(key)
      case 'redis_upstash':  return await testRedisUpstash(key, config.workspaceId)
      case 's3':             return await testS3(key, config.workspaceId)
      case 'tailscale':      return await testTailscale(key, config.workspaceId)
      case 'plausible':      return await testPlausible(key, config.workspaceId)
      case 'pushover':       return await testPushover(key)
      case 'twilio':         return await testTwilio(key)
      case 'hibp':           return await testHIBP(key)
      case 'abuseipdb':      return await testAbuseIPDB(key)
      case 'discogs':        return await testDiscogs(key)
      case 'igdb':           return await testIGDB(key)
      case 'apple_reminders':return await testAppleReminders()
      case 'stability_ai':   return await testStabilityAI(key)
      case 'mapbox':         return await testMapbox(key)
      case 'polygon':        return await testPolygon(key)
      case 'perplexity':     return await testPerplexity(key)
      case 'datadog':        return await testDatadog(key, config.workspaceId)
      case 'sentry':         return await testSentry(key)
      case 'habitica':       return await testHabitica(key)
      case 'algolia':        return await testAlgolia(key)
      case 'sendgrid':       return await testSendgrid(key)
      case 'cloudinary':     return await testCloudinary(key)
      case 'pinecone':       return await testPinecone(key, config.workspaceId)
      case 'mailchimp':      return await testMailchimp(key)
      case 'auth0':          return await testAuth0(key, config.workspaceId)
      case 'clerk':          return await testClerk(key)
      case 'mqtt':           return await testMqtt(key, config.workspaceId)
      case 'tuya':           return await testTuya(key, config.workspaceId)
      case 'tado':           return await testTado(key)
      case 'circleci':       return await testCircleCI(key)
      case 'wyze':           return await testWyze(key, config.workspaceId)
      case 'nodered':        return await testNodeRED(key, config.baseUrl)
      case 'bambu':          return await testBambu(key)
      case 'strava':         return await testStrava(key)
      case 'trello':         return await testTrello(key)
      case 'jira':           return await testJira(key, config.baseUrl)
      case 'wakatime':       return await testWakaTime(key)
      case 'plex':           return await testPlex(key, config.baseUrl)
      case 'grafana':        return await testGrafana(key, config.baseUrl)
      case 'hubspot':        return await testHubSpot(key)
      case 'toggl':          return await testToggl(key)
      case 'make_com':       return await testMakeCom(key)
      case 'machine_local':  return { ok: true, message: 'local execution via bridge OK' }
      case 'aurora_code':    return { ok: true, message: 'module Code interne dispo (qwen3-coder via Ollama)' }
      case 'aurora_3d':      return { ok: true, message: 'module 3D interne dispo (Hunyuan3D pipeline)' }
      case 'aurora_image':   return { ok: true, message: 'module Image interne dispo (FLUX/SDXL)' }
      case 'aurora_voice':   return { ok: true, message: 'module Voice interne dispo (TTS/STT)' }
      case 'aurora_video':   return { ok: true, message: 'module Video interne dispo' }
      case 'aurora_drawing': return { ok: true, message: 'module Drawing interne dispo' }
      case 'aurora_learning':return { ok: true, message: 'module Learning interne dispo' }
      case 'machine_pi':
      case 'machine_linux':
      case 'machine_ssh': {
        try {
          const r = await fetch(`${bridgeBase()}/api/connect/targets/list`)
          const data = await r.json() as { ok: boolean; targets: Array<{ name: string; platform?: string }> }
          const expectedPlatform = id === 'machine_pi' ? 'raspberry_pi' :
                                     id === 'machine_linux' ? 'linux_x86' : null
          const matching = data.targets.filter(t =>
            expectedPlatform === null || t.platform === expectedPlatform || t.platform === 'linux_arm' || !t.platform
          )
          if (matching.length === 0) {
            return { ok: false, message: `aucune cible ${id} configuree (POST /api/connect/targets/save)` }
          }
          return { ok: true, message: `${matching.length} cible(s) configuree(s): ${matching.map(t => t.name).join(', ')}` }
        } catch (e) {
          return { ok: false, message: `bridge non joignable: ${e instanceof Error ? e.message : String(e)}` }
        }
      }
      default: return { ok: false, message: `connecteur inconnu: ${id}` }
    }
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) }
  }
}

// === Test implementations ===
async function testGitHub(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.github.com/user', { headers: { Authorization: `Bearer ${t}`, Accept: 'application/vnd.github+json', 'User-Agent': 'AuroraIA' }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { login?: string }
  return { ok: true, message: `connecte: @${d.login}`, user: d.login }
}
async function testGitLab(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://gitlab.com/api/v4/user', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { username?: string }
  return { ok: true, message: `connecte: @${d.username}`, user: d.username }
}
async function testVercel(t: string, team?: string): Promise<ConnectorTestResult> {
  const url = team ? `https://api.vercel.com/v2/user?teamId=${encodeURIComponent(team)}` : 'https://api.vercel.com/v2/user'
  const r = await fetch(url, { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { user?: { username?: string } }
  return { ok: true, message: `connecte: ${d.user?.username}`, user: d.user?.username }
}
async function testNetlify(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.netlify.com/api/v1/user', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { email?: string; full_name?: string }
  return { ok: true, message: `connecte: ${d.full_name || d.email}` }
}
async function testCloudflare(t: string, _account?: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.cloudflare.com/client/v4/user', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { result?: { email?: string } }
  return { ok: true, message: `connecte: ${d.result?.email}` }
}
async function testRender(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.render.com/v1/services?limit=1', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'cle Render valide' }
}
async function testRailway(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://backboard.railway.app/graphql/v2', { method: 'POST', headers: { Authorization: `Bearer ${t}`, ...CT_JSON }, body: JSON.stringify({ query: '{ me { name } }' }), signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { me?: { name?: string } } }
  return { ok: true, message: `connecte: ${d.data?.me?.name}` }
}
async function testFly(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.fly.io/graphql', { method: 'POST', headers: { Authorization: `Bearer ${t}`, ...CT_JSON }, body: JSON.stringify({ query: '{ viewer { email } }' }), signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { viewer?: { email?: string } } }
  return { ok: true, message: `connecte: ${d.data?.viewer?.email}` }
}
async function testSupabase(t: string, baseUrl?: string): Promise<ConnectorTestResult> {
  if (!baseUrl) return { ok: false, message: 'baseUrl requise (https://<project>.supabase.co)' }
  const r = await fetch(`${baseUrl.replace(/\/$/, '')}/rest/v1/`, { headers: { apikey: t, Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Supabase valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testNotion(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.notion.com/v1/users/me', { headers: { Authorization: `Bearer ${t}`, 'Notion-Version': '2022-06-28' }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { name?: string }
  return { ok: true, message: `connecte: ${d.name}`, user: d.name }
}
async function testLinear(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.linear.app/graphql', { method: 'POST', headers: { Authorization: t.startsWith('lin_') ? t : `Bearer ${t}`, ...CT_JSON }, body: JSON.stringify({ query: '{ viewer { name } }' }), signal: AbortSignal.timeout(10_000) })
  const d = await r.json() as { data?: { viewer?: { name?: string } }; errors?: Array<{ message: string }> }
  if (d.errors?.length) return { ok: false, message: d.errors[0].message }
  return { ok: true, message: `connecte: ${d.data?.viewer?.name}` }
}
async function testAsana(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://app.asana.com/api/1.0/users/me', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { name?: string; email?: string } }
  return { ok: true, message: `connecte: ${d.data?.name || d.data?.email}` }
}
async function testTodoist(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.todoist.com/rest/v2/projects', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Todoist valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testSlack(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://slack.com/api/auth.test', { method: 'POST', headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  const d = await r.json() as { ok: boolean; team?: string; user?: string; error?: string }
  return d.ok ? { ok: true, message: `${d.user} @ ${d.team}`, user: d.user } : { ok: false, message: d.error || 'auth.test failed' }
}
async function testDiscord(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://discord.com/api/v10/users/@me', { headers: { Authorization: `Bot ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { username?: string }
  return { ok: true, message: `bot: ${d.username}`, user: d.username }
}
async function testTelegram(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://api.telegram.org/bot${encodeURIComponent(t)}/getMe`, { signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { ok: boolean; result?: { username?: string } }
  return d.ok ? { ok: true, message: `bot: @${d.result?.username}` } : { ok: false, message: 'getMe failed' }
}
async function testGoogleCalendar(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'token Google Calendar valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testGmail(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/profile', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { emailAddress?: string }
  return { ok: true, message: `connecte: ${d.emailAddress}` }
}
async function testGoogleDrive(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://www.googleapis.com/drive/v3/about?fields=user', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { user?: { emailAddress?: string } }
  return { ok: true, message: `connecte: ${d.user?.emailAddress}` }
}
async function testDropbox(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.dropboxapi.com/2/users/get_current_account', { method: 'POST', headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { email?: string; name?: { display_name?: string } }
  return { ok: true, message: `connecte: ${d.name?.display_name || d.email}` }
}
async function testSpotify(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.spotify.com/v1/me', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { display_name?: string; id?: string }
  return { ok: true, message: `connecte: ${d.display_name || d.id}` }
}
async function testYouTube(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&maxResults=1&key=${encodeURIComponent(t)}`, { signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle YouTube valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testHomeAssistant(t: string, baseUrl?: string): Promise<ConnectorTestResult> {
  const url = (baseUrl || 'http://homeassistant.local:8123').replace(/\/$/, '') + '/api/'
  const r = await fetch(url, { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'Home Assistant joignable' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testHue(_user: string, baseUrl?: string): Promise<ConnectorTestResult> {
  if (!baseUrl) return { ok: false, message: 'baseUrl Hue bridge requise' }
  const r = await fetch(`${baseUrl.replace(/\/$/, '')}/api/${encodeURIComponent(_user)}/lights`, { signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'Hue bridge joignable' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testOpenWeather(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=Paris&appid=${encodeURIComponent(t)}`, { signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle OpenWeather valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testDeepL(t: string): Promise<ConnectorTestResult> {
  const url = t.endsWith(':fx') ? 'https://api-free.deepl.com/v2/usage' : 'https://api.deepl.com/v2/usage'
  const r = await fetch(url, { headers: { Authorization: `DeepL-Auth-Key ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { character_count?: number; character_limit?: number }
  return { ok: true, message: `${d.character_count}/${d.character_limit} chars utilises` }
}
async function testMaps(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://maps.googleapis.com/maps/api/geocode/json?address=Paris&key=${encodeURIComponent(t)}`, { signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { status?: string }
  return d.status === 'OK' ? { ok: true, message: 'cle Maps valide' } : { ok: false, message: d.status || 'erreur' }
}
async function testHF(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://huggingface.co/api/whoami-v2', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { name?: string }
  return { ok: true, message: `connecte: ${d.name}` }
}
async function testReplicate(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.replicate.com/v1/account', { headers: { Authorization: `Token ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { username?: string }
  return { ok: true, message: `connecte: ${d.username}` }
}
async function testHorde(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://stablehorde.net/api/v2/find_user', { headers: { apikey: t }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { username?: string; kudos?: number }
  return { ok: true, message: `${d.username} (${d.kudos} kudos)` }
}
async function testMeshy(t: string): Promise<ConnectorTestResult> {
  // /v2/text-to-3d returns recent jobs — cheap auth check.
  const r = await fetch('https://api.meshy.ai/openapi/v2/text-to-3d?page_num=1&page_size=1', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'cle Meshy valide (200 credits/mois free tier)' }
}
async function testPostgres(dsn: string): Promise<ConnectorTestResult> {
  // Test via le bridge local (le DSN ne quitte jamais la machine).
  try {
    const { getBridgeUrl } = await import('../utils/runtime')
    const r = await fetch(`${getBridgeUrl()}/api/cowork/db/sql`, {
      method: 'POST',
      headers: CT_JSON,
      body: JSON.stringify({ dsn, sql: 'SELECT 1 AS ok', args: [] }),
      signal: AbortSignal.timeout(10_000),
    })
    if (!r.ok) return { ok: false, message: `bridge HTTP ${r.status}` }
    const d = await r.json() as { ok: boolean; rows?: unknown[]; error?: string }
    return d.ok ? { ok: true, message: 'connexion Postgres OK' } : { ok: false, message: d.error || 'erreur SQL' }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function testRedisUpstash(token: string, baseUrl?: string): Promise<ConnectorTestResult> {
  if (!baseUrl) return { ok: false, message: 'baseUrl Upstash requise (https://<db>.upstash.io)' }
  const r = await fetch(`${baseUrl.replace(/\/$/, '')}/ping`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { result?: string }
  return d.result === 'PONG' ? { ok: true, message: 'PONG (Redis Upstash OK)' } : { ok: false, message: `reponse inattendue: ${JSON.stringify(d).slice(0, 80)}` }
}
async function testS3(creds: string, endpoint?: string): Promise<ConnectorTestResult> {
  // Bridge gere la signature SigV4. On lui passe creds + endpoint + op=list_buckets.
  try {
    const { getBridgeUrl } = await import('../utils/runtime')
    const r = await fetch(`${getBridgeUrl()}/api/cowork/storage/s3`, {
      method: 'POST',
      headers: CT_JSON,
      body: JSON.stringify({ creds, endpoint: endpoint || 'https://s3.amazonaws.com', operation: 'list_buckets' }),
      signal: AbortSignal.timeout(15_000),
    })
    if (!r.ok) return { ok: false, message: `bridge HTTP ${r.status}` }
    const d = await r.json() as { ok: boolean; buckets?: string[]; error?: string }
    return d.ok ? { ok: true, message: `${(d.buckets || []).length} bucket(s) accessibles` } : { ok: false, message: d.error || 'erreur S3' }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function testTailscale(token: string, tailnet?: string): Promise<ConnectorTestResult> {
  const tn = tailnet || '-'
  const r = await fetch(`https://api.tailscale.com/api/v2/tailnet/${encodeURIComponent(tn)}/devices`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { devices?: Array<unknown> }
  return { ok: true, message: `${(d.devices || []).length} machines dans le tailnet` }
}
async function testPlausible(apiKey: string, siteId?: string): Promise<ConnectorTestResult> {
  if (!siteId) return { ok: false, message: 'site_id requis (workspaceId, ex: example.com)' }
  const r = await fetch(`https://plausible.io/api/v1/stats/realtime/visitors?site_id=${encodeURIComponent(siteId)}`, {
    headers: { Authorization: `Bearer ${apiKey}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const txt = await r.text()
  return { ok: true, message: `${txt.trim()} visiteurs en ce moment` }
}
async function testPushover(combo: string): Promise<ConnectorTestResult> {
  const [appToken, userKey] = combo.split(':')
  if (!appToken || !userKey) return { ok: false, message: 'format attendu: <app_token>:<user_key>' }
  const body = new URLSearchParams({ token: appToken, user: userKey })
  const r = await fetch('https://api.pushover.net/1/users/validate.json', { method: 'POST', body, signal: AbortSignal.timeout(10_000) })
  const d = await r.json() as { status: number; user?: string; errors?: string[] }
  return d.status === 1 ? { ok: true, message: `user_key valide (${d.user})` } : { ok: false, message: (d.errors || []).join(', ') || 'invalide' }
}
async function testTwilio(combo: string): Promise<ConnectorTestResult> {
  const [sid, token] = combo.split(':')
  if (!sid || !token) return { ok: false, message: 'format attendu: <Account SID>:<Auth Token>' }
  const auth = 'Basic ' + btoa(`${sid}:${token}`)
  const r = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}.json`, { headers: { Authorization: auth }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { friendly_name?: string; status?: string }
  return { ok: true, message: `${d.friendly_name} (${d.status})` }
}
async function testHIBP(t: string): Promise<ConnectorTestResult> {
  // HIBP requires a paid API key. Test by hitting /breaches (cheap).
  const r = await fetch('https://haveibeenpwned.com/api/v3/breaches?domain=adobe.com', {
    headers: { 'hibp-api-key': t, 'User-Agent': 'AuroraIA-Cowork' },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401) return { ok: false, message: 'API key invalide' }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'cle HIBP valide' }
}
async function testAbuseIPDB(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.abuseipdb.com/api/v2/check?ipAddress=8.8.8.8', {
    headers: { Key: t, Accept: 'application/json' },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { abuseConfidenceScore?: number } }
  return { ok: true, message: `cle valide (8.8.8.8 score: ${d.data?.abuseConfidenceScore ?? '?'})` }
}
async function testDiscogs(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.discogs.com/oauth/identity', {
    headers: { Authorization: `Discogs token=${t}`, 'User-Agent': 'AuroraIA-Cowork/1.0' },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { username?: string }
  return { ok: true, message: `connecte: ${d.username}`, user: d.username }
}
async function testIGDB(combo: string): Promise<ConnectorTestResult> {
  const [clientId, bearer] = combo.split(':')
  if (!clientId || !bearer) return { ok: false, message: 'format attendu: <client_id>:<bearer>' }
  const r = await fetch('https://api.igdb.com/v4/games', {
    method: 'POST',
    headers: { 'Client-ID': clientId, Authorization: `Bearer ${bearer}`, Accept: 'application/json' },
    body: 'fields name; limit 1;',
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'cles Twitch+IGDB valides' }
}
async function testStabilityAI(t: string): Promise<ConnectorTestResult> {
  // /v1/user/account is the cheapest auth check.
  const r = await fetch('https://api.stability.ai/v1/user/account', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { email?: string; credits?: number }
  return { ok: true, message: `connecte ${d.email} (${d.credits ?? '?'} credits)` }
}
async function testMapbox(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://api.mapbox.com/geocoding/v5/mapbox.places/Paris.json?access_token=${encodeURIComponent(t)}&limit=1`, {
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'token Mapbox valide' }
}
async function testPolygon(t: string): Promise<ConnectorTestResult> {
  const r = await fetch(`https://api.polygon.io/v3/reference/tickers/AAPL?apiKey=${encodeURIComponent(t)}`, {
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { results?: { name?: string } }
  return { ok: true, message: `cle Polygon valide (${d.results?.name})` }
}
async function testDatadog(combo: string, baseUrl?: string): Promise<ConnectorTestResult> {
  const [apiKey, appKey] = combo.split(':')
  if (!apiKey || !appKey) return { ok: false, message: 'format attendu: <api_key>:<app_key>' }
  const root = (baseUrl || 'https://api.datadoghq.com').replace(/\/$/, '')
  // /api/v1/validate is the cheapest auth check
  const r = await fetch(`${root}/api/v1/validate`, {
    headers: { 'DD-API-KEY': apiKey, 'DD-APPLICATION-KEY': appKey },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { valid?: boolean }
  return d.valid ? { ok: true, message: 'cles Datadog valides' } : { ok: false, message: 'invalid' }
}
async function testHabitica(combo: string): Promise<ConnectorTestResult> {
  const [userId, token] = combo.split(':')
  if (!userId || !token) return { ok: false, message: 'format <userId>:<apiToken>' }
  const r = await fetch('https://habitica.com/api/v3/user', {
    headers: { 'x-api-user': userId, 'x-api-key': token, 'x-client': 'AuroraIA-Cowork' },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { profile?: { name?: string }; stats?: { lvl?: number; gp?: number } } }
  return { ok: true, message: `connecte: ${d.data?.profile?.name} (lvl ${d.data?.stats?.lvl}, ${d.data?.stats?.gp?.toFixed(0)} gp)` }
}
async function testAlgolia(combo: string): Promise<ConnectorTestResult> {
  const [appId, key] = combo.split(':')
  if (!appId || !key) return { ok: false, message: 'format <AppId>:<SearchApiKey>' }
  const r = await fetch(`https://${appId}-dsn.algolia.net/1/indexes`, {
    headers: { 'X-Algolia-Application-Id': appId, 'X-Algolia-API-Key': key },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { items?: Array<{ name?: string }> }
  return { ok: true, message: `${(d.items || []).length} indexes accessibles` }
}
async function testSendgrid(t: string): Promise<ConnectorTestResult> {
  // /v3/scopes is the cheapest auth check
  const r = await fetch('https://api.sendgrid.com/v3/scopes', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { scopes?: string[] }
  return { ok: true, message: `cle SendGrid valide (${(d.scopes || []).length} scopes)` }
}
async function testPinecone(t: string, host?: string): Promise<ConnectorTestResult> {
  // /describe_index_stats is the cheapest auth check on the index host
  if (!host) return { ok: false, message: 'baseUrl (host de l index) requis' }
  const r = await fetch(`${host.replace(/\/$/, '')}/describe_index_stats`, {
    method: 'POST',
    headers: { 'Api-Key': t, 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { totalVectorCount?: number; dimension?: number }
  return { ok: true, message: `index OK (${d.totalVectorCount ?? '?'} vectors, dim ${d.dimension ?? '?'})` }
}
async function testMailchimp(t: string): Promise<ConnectorTestResult> {
  // The DC suffix tells us the server : key xxx-us21 -> us21.api.mailchimp.com
  const dc = (t.split('-')[1] || 'us1').trim()
  const r = await fetch(`https://${dc}.api.mailchimp.com/3.0/ping`, {
    headers: { Authorization: `apikey ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { health_status?: string }
  return { ok: true, message: d.health_status || 'pong' }
}
async function testAuth0(t: string, tenantBaseUrl?: string): Promise<ConnectorTestResult> {
  const base = (tenantBaseUrl || '').replace(/\/$/, '')
  if (!base) return { ok: false, message: 'baseUrl tenant requis (https://<tenant>.auth0.com)' }
  const r = await fetch(`${base}/api/v2/users?per_page=1`, {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'token Auth0 Management API valide' }
}
async function testMqtt(creds: string, baseUrl?: string): Promise<ConnectorTestResult> {
  if (!baseUrl) return { ok: false, message: 'baseUrl broker requis (mqtt://host:1883)' }
  try {
    const { getBridgeUrl } = await import('../utils/runtime')
    const r = await fetch(`${getBridgeUrl()}/api/cowork/iot/mqtt`, {
      method: 'POST',
      headers: CT_JSON,
      body: JSON.stringify({ broker: baseUrl, auth: creds, operation: 'test' }),
      signal: AbortSignal.timeout(15_000),
    })
    if (!r.ok) return { ok: false, message: `bridge HTTP ${r.status}` }
    const d = await r.json() as { ok: boolean; error?: string }
    return d.ok ? { ok: true, message: 'connexion broker OK' } : { ok: false, message: d.error || 'connection failed' }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function testTuya(combo: string, baseUrl?: string): Promise<ConnectorTestResult> {
  // Tuya needs HMAC signing — we just check creds format here, the real
  // signing happens server-side or in run.
  const [accessKey, secret] = combo.split(':')
  if (!accessKey || !secret) return { ok: false, message: 'format <AccessKey>:<Secret>' }
  if (!baseUrl) return { ok: false, message: 'baseUrl region requise (tuyaeu/tuyaus/tuyacn)' }
  // We attempt /v1.0/token (HMAC sig) — if creds invalid, returns 1011 error.
  try {
    const t = String(Math.floor(Date.now()))
    const sign = await tuyaSign(accessKey, secret, t, 'GET', '/v1.0/token?grant_type=1')
    const r = await fetch(`${baseUrl.replace(/\/$/, '')}/v1.0/token?grant_type=1`, {
      headers: {
        client_id: accessKey,
        access_token: '',
        sign,
        t,
        sign_method: 'HMAC-SHA256',
      },
      signal: AbortSignal.timeout(10_000),
    })
    const d = await r.json() as { success?: boolean; msg?: string }
    return d.success ? { ok: true, message: 'cles Tuya valides' } : { ok: false, message: d.msg || 'echec' }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function tuyaSign(accessKey: string, secret: string, t: string, method: string, path: string): Promise<string> {
  // contentSha256 = sha256("") = e3b0c44...
  const emptySha = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  const stringToSign = `${method}\n${emptySha}\n\n${path}`
  const signStr = accessKey + t + stringToSign
  const enc = new TextEncoder()
  const keyData = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const sigBuf = await crypto.subtle.sign('HMAC', keyData, enc.encode(signStr))
  return Array.from(new Uint8Array(sigBuf)).map((b) => b.toString(16).padStart(2, '0').toUpperCase()).join('')
}
async function testTado(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://my.tado.com/api/v2/me', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { name?: string; email?: string; homes?: Array<{ id: number }> }
  return { ok: true, message: `connecte: ${d.name || d.email} (${(d.homes ?? []).length} homes)` }
}
async function testCircleCI(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://circleci.com/api/v2/me', {
    headers: { 'Circle-Token': t },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { login?: string; name?: string }
  return { ok: true, message: `connecte: ${d.login || d.name}` }
}
// === v14 tests ===
async function testWyze(combo: string, _baseUrl?: string): Promise<ConnectorTestResult> {
  // Wyze requires apikey + keyid. We expect "<apikey>:<keyid>" in the credential.
  const [apikey, keyid] = (combo || '').split(':')
  if (!apikey || !keyid) return { ok: false, message: 'format requis: <apikey>:<keyid>' }
  // Hit a cheap endpoint : list devices, paginated to 1.
  const r = await fetch('https://api.wyzecam.com/app/v2/home_page/get_object_list', {
    method: 'POST',
    headers: { ...CT_JSON, 'apikey': apikey, 'keyid': keyid },
    body: JSON.stringify({ phone_id: 'aurora-ai' }),
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'apikey + keyid Wyze valides' }
}
async function testNodeRED(t: string, base?: string): Promise<ConnectorTestResult> {
  const root = (base ?? 'http://127.0.0.1:1880').replace(/\/+$/, '')
  // /flows requires admin auth. Try with bearer if provided, else hit /
  const headers: Record<string, string> = {}
  if (t) headers.Authorization = `Bearer ${t}`
  const r = await fetch(`${root}/`, { headers, signal: AbortSignal.timeout(8_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status} ${root}` }
  const txt = await r.text()
  if (!/Node-?RED/i.test(txt)) return { ok: false, message: 'Reponse pas Node-RED — verifie baseUrl' }
  return { ok: true, message: `Node-RED accessible @ ${root}` }
}
async function testBambu(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.bambulab.com/v1/iot-service/api/user/bind', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401 || r.status === 403) return { ok: false, message: `auth refusee (${r.status})` }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'bearer Bambu valide' }
}
async function testStrava(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://www.strava.com/api/v3/athlete', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401) return { ok: false, message: 'token Strava invalide ou expire — refresh OAuth requis' }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { id?: number; firstname?: string; lastname?: string }
  return { ok: true, message: `connecte: ${d.firstname} ${d.lastname} (id ${d.id})` }
}
// === v15 tests ===
async function testTrello(combo: string): Promise<ConnectorTestResult> {
  const [key, token] = (combo || '').split(':')
  if (!key || !token) return { ok: false, message: 'format requis: <KEY>:<TOKEN>' }
  const r = await fetch(`https://api.trello.com/1/members/me?key=${encodeURIComponent(key)}&token=${encodeURIComponent(token)}`, {
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { fullName?: string; username?: string }
  return { ok: true, message: `connecte: ${d.fullName || d.username}` }
}
async function testJira(combo: string, base?: string): Promise<ConnectorTestResult> {
  if (!base) return { ok: false, message: 'baseUrl requis (https://<workspace>.atlassian.net)' }
  const [email, token] = (combo || '').split(':')
  if (!email || !token) return { ok: false, message: 'format requis: <email>:<TOKEN>' }
  const auth = 'Basic ' + btoa(`${email}:${token}`)
  const root = base.replace(/\/+$/, '')
  const r = await fetch(`${root}/rest/api/3/myself`, {
    headers: { Authorization: auth, Accept: 'application/json' },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { displayName?: string; emailAddress?: string }
  return { ok: true, message: `connecte: ${d.displayName || d.emailAddress}` }
}
async function testWakaTime(t: string): Promise<ConnectorTestResult> {
  const auth = 'Basic ' + btoa(`${t}:`)
  const r = await fetch('https://wakatime.com/api/v1/users/current', {
    headers: { Authorization: auth },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { data?: { display_name?: string; username?: string } }
  return { ok: true, message: `connecte: ${d.data?.display_name || d.data?.username}` }
}
async function testPlex(t: string, base?: string): Promise<ConnectorTestResult> {
  const root = (base ?? 'http://127.0.0.1:32400').replace(/\/+$/, '')
  const r = await fetch(`${root}/?X-Plex-Token=${encodeURIComponent(t)}`, {
    headers: { Accept: 'application/json' },
    signal: AbortSignal.timeout(8_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status} ${root}` }
  return { ok: true, message: `Plex accessible @ ${root}` }
}
// === v16 tests ===
async function testGrafana(t: string, base?: string): Promise<ConnectorTestResult> {
  const root = (base ?? 'http://127.0.0.1:3000').replace(/\/+$/, '')
  const r = await fetch(`${root}/api/user`, {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401) return { ok: false, message: 'token Grafana invalide' }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status} ${root}` }
  const d = await r.json() as { login?: string; email?: string }
  return { ok: true, message: `connecte: ${d.login || d.email}` }
}
async function testHubSpot(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.hubapi.com/crm/v3/objects/contacts?limit=1', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401) return { ok: false, message: 'token HubSpot invalide / scopes insuffisants' }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'token HubSpot valide' }
}
// === v18 tests ===
async function testToggl(t: string): Promise<ConnectorTestResult> {
  const auth = 'Basic ' + btoa(`${t}:api_token`)
  const r = await fetch('https://api.track.toggl.com/api/v9/me', {
    headers: { Authorization: auth },
    signal: AbortSignal.timeout(10_000),
  })
  if (r.status === 401 || r.status === 403) return { ok: false, message: 'token Toggl invalide' }
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { fullname?: string; email?: string }
  return { ok: true, message: `connecte: ${d.fullname || d.email}` }
}
async function testMakeCom(url: string): Promise<ConnectorTestResult> {
  if (!url || !/^https:\/\/hook\.([a-z0-9-]+\.)?make\.com\//i.test(url)) {
    return { ok: false, message: 'URL invalide. Format attendu : https://hook.<region>.make.com/...' }
  }
  // Don't actually trigger the scenario — just verify the host responds.
  // Make.com webhooks accept GET pings (200 OK with "Accepted" body).
  try {
    const r = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(8_000) })
    if (r.status === 410) return { ok: false, message: 'webhook supprime cote Make.com (410 Gone)' }
    return r.ok || r.status === 400  // some hooks return 400 on empty body but URL is valid
      ? { ok: true, message: 'webhook Make.com joignable' }
      : { ok: false, message: `HTTP ${r.status}` }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function testClerk(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.clerk.com/v1/users?limit=1', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'cle Clerk valide' }
}
async function testCloudinary(combo: string): Promise<ConnectorTestResult> {
  const [cloud, key, secret] = combo.split(':')
  if (!cloud || !key || !secret) return { ok: false, message: 'format <CloudName>:<ApiKey>:<ApiSecret>' }
  const auth = 'Basic ' + btoa(`${key}:${secret}`)
  const r = await fetch(`https://api.cloudinary.com/v1_1/${cloud}/usage`, {
    headers: { Authorization: auth },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { storage?: { usage?: number }; bandwidth?: { usage?: number } }
  return { ok: true, message: `Cloudinary OK (storage ${(d.storage?.usage ?? 0).toFixed(0)} octets)` }
}
async function testSentry(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://sentry.io/api/0/organizations/', {
    headers: { Authorization: `Bearer ${t}` },
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as Array<{ name?: string; slug?: string }>
  return { ok: true, message: `${d.length} org(s) accessibles${d[0]?.slug ? `, premiere: ${d[0].slug}` : ''}` }
}
async function testPerplexity(t: string): Promise<ConnectorTestResult> {
  // Cheapest test: 1-token chat completion.
  const r = await fetch('https://api.perplexity.ai/chat/completions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'sonar',
      max_tokens: 1,
      messages: [{ role: 'user', content: 'hi' }],
    }),
    signal: AbortSignal.timeout(15_000),
  })
  if (r.status === 401 || r.status === 403) return { ok: false, message: `auth refusee (${r.status})` }
  return { ok: true, message: 'cle Perplexity valide' }
}
async function testAppleReminders(): Promise<ConnectorTestResult> {
  // Pas de cle externe : on verifie qu au moins une extension mobile poll
  // le bridge actuellement (= raccourci iOS lance).
  try {
    const { getBridgeUrl } = await import('../utils/runtime')
    const r = await fetch(`${getBridgeUrl()}/api/cowork/mobile/events`, { signal: AbortSignal.timeout(5_000) })
    if (!r.ok) return { ok: false, message: `bridge HTTP ${r.status}` }
    const d = await r.json() as { events?: Array<{ at?: number }> }
    const last = (d.events ?? []).slice(-1)[0]
    const fresh = last?.at ? (Date.now() / 1000 - last.at) < 600 : false
    return fresh
      ? { ok: true, message: 'raccourci iOS detecte (poll mobile actif < 10min)' }
      : { ok: true, message: 'raccourci iOS pas encore detecte. Importe aurora-ios-shortcuts.json et lance Aurora Poll.' }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}
async function testBrave(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.search.brave.com/res/v1/web/search?q=test&count=1', { headers: { 'X-Subscription-Token': t, Accept: 'application/json' }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Brave Search valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testCanva(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.canva.com/rest/v1/users/me', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  return { ok: true, message: 'token Canva valide' }
}
async function testFigma(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.figma.com/v1/me', { headers: { 'X-Figma-Token': t }, signal: AbortSignal.timeout(10_000) })
  if (!r.ok) return { ok: false, message: `HTTP ${r.status}` }
  const d = await r.json() as { handle?: string; email?: string }
  return { ok: true, message: `connecte: ${d.handle || d.email}` }
}
async function testStripe(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.stripe.com/v1/customers?limit=1', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Stripe valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testOpenAI(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.openai.com/v1/models?limit=1', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle OpenAI valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testAnthropic(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': t, 'anthropic-version': '2023-06-01', ...CT_JSON },
    body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] }),
    signal: AbortSignal.timeout(15_000),
  })
  if (r.status === 401 || r.status === 403) return { ok: false, message: `auth refusee (${r.status})` }
  return { ok: true, message: 'cle Anthropic valide' }
}
async function testMistral(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.mistral.ai/v1/models', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Mistral valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testGroq(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://api.groq.com/openai/v1/models', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle Groq valide' } : { ok: false, message: `HTTP ${r.status}` }
}
async function testOpenRouter(t: string): Promise<ConnectorTestResult> {
  const r = await fetch('https://openrouter.ai/api/v1/models', { headers: { Authorization: `Bearer ${t}` }, signal: AbortSignal.timeout(10_000) })
  return r.ok ? { ok: true, message: 'cle OpenRouter valide' } : { ok: false, message: `HTTP ${r.status}` }
}

// ---------------------------------------------------------------------------
// Action runner — generic dispatcher.
// ---------------------------------------------------------------------------

export async function runConnectorAction(
  id: ConnectorId,
  action: string,
  params: Record<string, unknown>,
  config: { apiKey?: string; baseUrl?: string; workspaceId?: string },
): Promise<ConnectorRunResult> {
  const key = (config.apiKey || '').trim()
  // Public APIs that don't need a key (SSH creds are stored bridge-side per target).
  const publicAPIs = new Set<ConnectorId>([
    'wikipedia', 'arxiv', 'hackernews', 'reddit',
    'machine_local', 'machine_pi', 'machine_linux', 'machine_ssh',
    'aurora_code', 'aurora_3d', 'aurora_image', 'aurora_voice',
    'aurora_video', 'aurora_drawing', 'aurora_learning',
  ])
  if (!key && !publicAPIs.has(id)) {
    return { ok: false, error: `${id}: API key non configuree (Settings -> Connecteurs)` }
  }

  try {
    switch (id) {
      case 'github':         return await runGitHub(action, params, key)
      case 'vercel':         return await runVercel(action, params, key, config.workspaceId)
      case 'notion':         return await runNotion(action, params, key)
      case 'linear':         return await runLinear(action, params, key)
      case 'slack':          return await runSlack(action, params, key)
      case 'discord':        return await runDiscord(action, params, key)
      case 'telegram':       return await runTelegram(action, params, key)
      case 'todoist':        return await runTodoist(action, params, key)
      case 'spotify':        return await runSpotify(action, params, key)
      case 'youtube':        return await runYouTube(action, params, key)
      case 'home_assistant': return await runHomeAssistant(action, params, key, config.workspaceId)
      case 'openweather':    return await runOpenWeather(action, params, key)
      case 'translate_deepl':return await runDeepL(action, params, key)
      case 'wikipedia':      return await runWikipedia(action, params)
      case 'arxiv':          return await runArxiv(action, params)
      case 'hackernews':     return await runHN(action, params)
      case 'reddit':         return await runReddit(action, params)
      case 'huggingface':    return await runHF(action, params, key)
      case 'replicate':      return await runReplicate(action, params, key)
      case 'stable_horde':   return await runHorde(action, params, key)
      case 'meshy':          return await runMeshy(action, params, key)
      case 'postgres':       return await runPostgres(action, params, key)
      case 'redis_upstash':  return await runRedisUpstash(action, params, key, config.workspaceId)
      case 's3':             return await runS3(action, params, key, config.workspaceId)
      case 'tailscale':      return await runTailscale(action, params, key, config.workspaceId)
      case 'plausible':      return await runPlausible(action, params, key, config.workspaceId)
      case 'pushover':       return await runPushover(action, params, key)
      case 'twilio':         return await runTwilio(action, params, key, config.workspaceId)
      case 'openstreetmap':  return await runOSM(action, params)
      case 'hibp':           return await runHIBP(action, params, key)
      case 'abuseipdb':      return await runAbuseIPDB(action, params, key)
      case 'discogs':        return await runDiscogs(action, params, key)
      case 'igdb':           return await runIGDB(action, params, key)
      case 'openlibrary':    return await runOpenLibrary(action, params)
      case 'apple_reminders':return await runAppleReminders(action, params)
      case 'stability_ai':   return await runStabilityAI(action, params, key)
      case 'mapbox':         return await runMapbox(action, params, key)
      case 'coingecko':      return await runCoinGecko(action, params, key)
      case 'polygon':        return await runPolygon(action, params, key)
      case 'perplexity':     return await runPerplexity(action, params, key)
      case 'datadog':        return await runDatadog(action, params, key, config.workspaceId)
      case 'sentry':         return await runSentry(action, params, key, config.workspaceId)
      case 'habitica':       return await runHabitica(action, params, key)
      case 'algolia':        return await runAlgolia(action, params, key, config.workspaceId)
      case 'sendgrid':       return await runSendgrid(action, params, key)
      case 'cloudinary':     return await runCloudinary(action, params, key)
      case 'pinecone':       return await runPinecone(action, params, key, config.workspaceId)
      case 'mailchimp':      return await runMailchimp(action, params, key)
      case 'auth0':          return await runAuth0(action, params, key, config.workspaceId)
      case 'clerk':          return await runClerk(action, params, key)
      case 'mqtt':           return await runMqtt(action, params, key, config.workspaceId)
      case 'tuya':           return await runTuya(action, params, key, config.workspaceId)
      case 'tado':           return await runTado(action, params, key)
      case 'circleci':       return await runCircleCI(action, params, key)
      case 'wyze':           return await runWyze(action, params, key, config.workspaceId)
      case 'nodered':        return await runNodeRED(action, params, key, config.baseUrl)
      case 'bambu':          return await runBambu(action, params, key)
      case 'strava':         return await runStrava(action, params, key)
      case 'trello':         return await runTrello(action, params, key)
      case 'jira':           return await runJira(action, params, key, config.baseUrl)
      case 'wakatime':       return await runWakaTime(action, params, key)
      case 'plex':           return await runPlex(action, params, key, config.baseUrl)
      case 'grafana':        return await runGrafana(action, params, key, config.baseUrl)
      case 'hubspot':        return await runHubSpot(action, params, key)
      case 'toggl':          return await runToggl(action, params, key)
      case 'make_com':       return await runMakeCom(action, params, key)
      case 'brave_search':   return await runBrave(action, params, key)
      case 'figma':          return await runFigma(action, params, key)
      case 'stripe':         return await runStripe(action, params, key)
      case 'openai':         return await runOpenAI(action, params, key)
      case 'anthropic':      return await runAnthropic(action, params, key)
      case 'mistral':        return await runMistral(action, params, key)
      case 'groq':           return await runGroq(action, params, key)
      case 'openrouter':     return await runOpenRouter(action, params, key)
      case 'machine_local':
      case 'machine_pi':
      case 'machine_linux':
      case 'machine_ssh':    return await runMachine(id, action, params)
      case 'aurora_code':
      case 'aurora_3d':
      case 'aurora_image':
      case 'aurora_voice':
      case 'aurora_video':
      case 'aurora_drawing':
      case 'aurora_learning': return await runAuroraModule(id, action, params)
      default:               return { ok: false, error: `${id}: action handler not yet implemented (try test only)` }
    }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

// === Run implementations (compact) ===

/**
 * runAuroraModule — dispatcher for internal Aurora capabilities (code, 3D,
 * image, voice, video, drawing, learning). Routes through the bridge so the
 * existing Python pipelines can serve the request. The cowork planner LLM
 * sees these in the connector registry just like any external API and can
 * compose them: "generate a logo with aurora_image, make a 3D version with
 * aurora_3d, deploy with machine_pi".
 *
 * Each module exposes the same {ok, data, output} contract.
 */
async function runAuroraModule(id: ConnectorId, action: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  const module = id.replace('aurora_', '')
  try {
    const r = await fetch(`${bridgeBase()}/api/aurora/${module}/${action}`, {
      method: 'POST',
      headers: CT_JSON,
      body: JSON.stringify(p),
    })
    if (r.status === 404) {
      return {
        ok: false,
        error: `aurora_${module}.${action}: bridge endpoint /api/aurora/${module}/${action} introuvable — vérifie que bridge_server.py est à jour (le dispatcher /api/aurora/<module>/<action> doit exister).`,
      }
    }
    const data = await r.json() as Record<string, unknown>
    return {
      ok: !!data.ok,
      data,
      output: String(data.output ?? data.message ?? data.error ?? ''),
      error: data.ok ? undefined : String(data.error ?? 'unknown'),
    }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

async function runMachine(id: ConnectorId, action: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  const target_name = (p.target_name as string | undefined) || (id === 'machine_local' ? undefined : undefined)
  const post = async (path: string, body: unknown) => {
    const r = await fetch(`${bridgeBase()}/api/connect${path}`, {
      method: 'POST', headers: CT_JSON, body: JSON.stringify(body),
    })
    return r.json() as Promise<Record<string, unknown>>
  }
  try {
    if (id === 'machine_local') {
      switch (action) {
        case 'run': {
          // local execution goes through the bridge's existing shell endpoint.
          const r = await post('/ssh/run', {
            target_name: target_name || 'localhost', command: String(p.command || ''),
            timeout: p.timeout ?? 60,
          })
          return { ok: !!r.ok, data: r, output: String((r.stdout as string) || (r.error as string) || '') }
        }
        default:
          return { ok: false, error: `machine_local: action ${action} not supported (run only)` }
      }
    }
    // SSH-based targets
    switch (action) {
      case 'probe': {
        const r = await post('/ssh/probe', { target_name, ...p })
        return { ok: !!r.ok, data: r, output: String((r.out as string) || (r.error as string) || '') }
      }
      case 'run': {
        const r = await post('/ssh/run', {
          target_name, command: String(p.command || ''), timeout: p.timeout ?? 60,
        })
        return { ok: !!r.ok, data: r, output: String((r.stdout as string) || (r.stderr as string) || '') }
      }
      case 'upload':
      case 'deploy_project': {
        // Single file upload: p.content can be string OR an array of {path,content} for deploy_project
        if (action === 'deploy_project' && Array.isArray(p.files)) {
          const slug = String(p.slug || `aurora-${Date.now()}`)
          const targets = await (await fetch(`${bridgeBase()}/api/connect/targets/list`)).json()
          const t = (targets.targets as Array<Record<string, unknown>> || []).find(x => x.name === target_name)
          const base = `${(t?.deploy_path as string) || '/tmp/aurora'}/${slug}`
          let uploaded = 0
          const errors: string[] = []
          for (const f of p.files as Array<{ path: string; content: string }>) {
            const remote = `${base}/${f.path.replace(/^\//, '')}`
            const bin = new TextEncoder().encode(f.content)
            let bs = ''
            for (let i = 0; i < bin.length; i++) bs += String.fromCharCode(bin[i])
            const r = await post('/ssh/upload', {
              target_name, remote_path: remote, content_b64: btoa(bs),
            })
            if (r.ok) uploaded++; else errors.push(`${f.path}: ${r.error}`)
          }
          return { ok: errors.length === 0, data: { uploaded, total: (p.files as unknown[]).length, errors, deploy_path: base } }
        }
        const content = String(p.content || '')
        const bin = new TextEncoder().encode(content)
        let bs = ''
        for (let i = 0; i < bin.length; i++) bs += String.fromCharCode(bin[i])
        const r = await post('/ssh/upload', {
          target_name, remote_path: String(p.remote_path || ''), content_b64: btoa(bs),
        })
        return { ok: !!r.ok, data: r }
      }
      case 'tcp_probe': {
        const r = await post('/tcp/probe', {
          host: String(p.host || ''), port: Number(p.port || 0), timeout: p.timeout ?? 4,
        })
        return { ok: !!r.ok, data: r }
      }
      case 'keygen': {
        const r = await post('/ssh/keygen', { comment: String(p.comment || 'aurora') })
        return { ok: !!r.ok, data: r, output: String((r.public_key as string) || (r.error as string) || '') }
      }
      case 'install_pkg': {
        // tries apt, then yum, then pacman
        const pkg = String(p.package_name || '')
        const cmd = `(command -v apt && sudo apt-get install -y ${pkg}) || (command -v yum && sudo yum install -y ${pkg}) || (command -v pacman && sudo pacman -S --noconfirm ${pkg})`
        const r = await post('/ssh/run', { target_name, command: cmd, timeout: 180 })
        return { ok: !!r.ok, data: r, output: String((r.stdout as string) || '') }
      }
      case 'start_service': {
        const svc = String(p.service_name || '')
        const r = await post('/ssh/run', { target_name, command: `sudo systemctl start ${svc} && systemctl status ${svc} --no-pager | head -10`, timeout: 30 })
        return { ok: !!r.ok, data: r, output: String((r.stdout as string) || '') }
      }
      case 'gpio_blink': {
        const pin = Number(p.pin || 17), count = Number(p.count || 5)
        const py = `python3 -c "import time
try:
    from gpiozero import LED
    led = LED(${pin})
    for _ in range(${count}):
        led.on(); time.sleep(0.3); led.off(); time.sleep(0.3)
    print('ok')
except Exception as e:
    print('ERR', e)"`
        const r = await post('/ssh/run', { target_name, command: py, timeout: 30 })
        return { ok: !!r.ok, data: r, output: String((r.stdout as string) || '') }
      }
      case 'camera_snap': {
        const out = String(p.out_path || '/tmp/aurora_cam.jpg')
        const cmd = `libcamera-still -o ${out} --timeout 200 --width 1280 --height 720 && echo SAVED ${out}`
        const r = await post('/ssh/run', { target_name, command: cmd, timeout: 15 })
        return { ok: !!r.ok, data: r, output: String((r.stdout as string) || '') }
      }
      default:
        return { ok: false, error: `${id}: action ${action} non implementee` }
    }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

async function runGitHub(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, Accept: 'application/vnd.github+json', 'User-Agent': 'AuroraIA' }
  const owner = String(p.owner ?? ''), repo = String(p.repo ?? '')
  switch (a) {
    case 'list_repos': return jsonGet('https://api.github.com/user/repos?per_page=30&sort=updated', auth)
    case 'get_repo':   return jsonGet(`https://api.github.com/repos/${owner}/${repo}`, auth)
    case 'list_issues': return jsonGet(`https://api.github.com/repos/${owner}/${repo}/issues?state=open&per_page=30`, auth)
    case 'create_issue': return jsonPost(`https://api.github.com/repos/${owner}/${repo}/issues`, { ...auth, ...CT_JSON }, { title: p.title, body: p.body })
    case 'list_prs':   return jsonGet(`https://api.github.com/repos/${owner}/${repo}/pulls?state=open&per_page=30`, auth)
    case 'merge_pr':   return jsonPost(`https://api.github.com/repos/${owner}/${repo}/pulls/${p.pull_number}/merge`, { ...auth, ...CT_JSON }, {})
    case 'search_code': return jsonGet(`https://api.github.com/search/code?q=${encodeURIComponent(String(p.q ?? ''))}`, auth)
    // === GitHub Actions logs (v13.2) ===
    case 'list_workflows': return jsonGet(`https://api.github.com/repos/${owner}/${repo}/actions/workflows?per_page=30`, auth)
    case 'list_workflow_runs': {
      const wfId = p.workflow_id ?? p.workflowId
      const status = p.status ? `&status=${encodeURIComponent(String(p.status))}` : ''
      const branch = p.branch ? `&branch=${encodeURIComponent(String(p.branch))}` : ''
      const url = wfId
        ? `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${wfId}/runs?per_page=20${status}${branch}`
        : `https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=20${status}${branch}`
      return jsonGet(url, auth)
    }
    case 'get_run_logs': {
      // Logs are returned as a zip archive. We download as a Blob, then return
      // size + a hint to the LLM (LLMs don t read binary). For real text
      // extraction the user should chain `shell unzip` or use rerun_workflow.
      const runId = p.run_id ?? p.runId
      if (!runId) return { ok: false, error: 'list_workflow_runs.run_id manquant' }
      try {
        const r = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/logs`, {
          headers: auth, redirect: 'follow', signal: AbortSignal.timeout(30_000),
        })
        if (!r.ok) return { ok: false, error: `HTTP ${r.status}` }
        const buf = await r.arrayBuffer()
        const sizeKB = Math.round(buf.byteLength / 1024)
        return {
          ok: true,
          output: `Logs run #${runId} : zip ${sizeKB} KB recupere. Pour le contenu : extrais via shell "curl -L -H 'Authorization: Bearer XXX' ... | bsdtar -xOf -" ou pivote sur la conclusion du run via list_workflow_runs.`,
          data: { runId, sizeKB, contentType: r.headers.get('content-type') },
        }
      } catch (e) {
        return { ok: false, error: e instanceof Error ? e.message : String(e) }
      }
    }
    case 'rerun_workflow': {
      const runId = p.run_id ?? p.runId
      if (!runId) return { ok: false, error: 'rerun_workflow.run_id manquant' }
      const r = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/rerun`, {
        method: 'POST', headers: { ...auth, ...CT_JSON },
      })
      return r.ok ? { ok: true, output: `Rerun lance pour run #${runId}` } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `github action inconnue: ${a}` }
  }
}
async function runVercel(a: string, p: Record<string, unknown>, t: string, team?: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}` }
  const tq = team ? `&teamId=${encodeURIComponent(team)}` : ''
  switch (a) {
    case 'list_projects': return jsonGet(`https://api.vercel.com/v9/projects?limit=30${tq}`, auth)
    case 'list_deployments': return jsonGet(`https://api.vercel.com/v6/deployments?projectId=${p.projectId}&limit=20${tq}`, auth)
    default: return { ok: false, error: `vercel action inconnue: ${a}` }
  }
}
async function runNotion(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const h = { Authorization: `Bearer ${t}`, 'Notion-Version': '2022-06-28', ...CT_JSON }
  switch (a) {
    case 'search':    return jsonPost('https://api.notion.com/v1/search', h, { query: p.query })
    case 'get_page':  return jsonGet(`https://api.notion.com/v1/pages/${p.pageId}`, h)
    case 'create_page': return jsonPost('https://api.notion.com/v1/pages', h, p)
    case 'query_db':  return jsonPost(`https://api.notion.com/v1/databases/${p.databaseId}/query`, h, p.filter ? { filter: p.filter } : {})
    default: return { ok: false, error: `notion action inconnue: ${a}` }
  }
}
async function runLinear(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: t.startsWith('lin_') ? t : `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_issues': return jsonPost('https://api.linear.app/graphql', auth, { query: '{ issues(first: 30) { nodes { id title state { name } estimate } } }' })
    case 'create_issue': return jsonPost('https://api.linear.app/graphql', auth, { query: 'mutation($t:String!,$tm:String!){issueCreate(input:{title:$t,teamId:$tm}){issue{id url}}}', variables: { t: p.title, tm: p.teamId } })
    case 'update_issue': return jsonPost('https://api.linear.app/graphql', auth, { query: 'mutation($id:String!,$st:String,$est:Float){issueUpdate(id:$id,input:{stateId:$st,estimate:$est}){success issue{id estimate}}}', variables: { id: p.id, st: p.stateId ?? null, est: p.estimate ?? null } })
    case 'get_issue_history': return jsonPost('https://api.linear.app/graphql', auth, { query: 'query($id:String!){issue(id:$id){id title estimate history{nodes{id createdAt fromState{name} toState{name}}} comments{nodes{id body createdAt user{name}}}}}', variables: { id: p.id } })
    case 'list_time_entries': return jsonPost('https://api.linear.app/graphql', auth, { query: 'query($id:String!){issue(id:$id){id title estimate comments(first:50){nodes{id body createdAt}}}}', variables: { id: p.id } })
    case 'add_comment': return jsonPost('https://api.linear.app/graphql', auth, { query: 'mutation($id:String!,$b:String!){commentCreate(input:{issueId:$id,body:$b}){success comment{id}}}', variables: { id: p.issueId, b: p.body } })
    default: return { ok: false, error: `linear action inconnue: ${a}` }
  }
}
async function runSlack(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'send_message': {
      const r = await fetch('https://slack.com/api/chat.postMessage', { method: 'POST', headers: auth, body: JSON.stringify({ channel: p.channel, text: p.text }) })
      const d = await r.json() as { ok: boolean; error?: string }
      return { ok: d.ok, data: d, error: d.ok ? undefined : d.error }
    }
    case 'list_channels': return jsonGet('https://slack.com/api/conversations.list?limit=100', { Authorization: `Bearer ${t}` })
    default: return { ok: false, error: `slack action inconnue: ${a}` }
  }
}
async function runDiscord(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bot ${t}`, ...CT_JSON }
  switch (a) {
    case 'send_message': return jsonPost(`https://discord.com/api/v10/channels/${p.channelId}/messages`, auth, { content: p.content })
    case 'list_guilds':  return jsonGet('https://discord.com/api/v10/users/@me/guilds', auth)
    default: return { ok: false, error: `discord action inconnue: ${a}` }
  }
}
async function runTelegram(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  switch (a) {
    case 'send_message': return jsonPost(`https://api.telegram.org/bot${encodeURIComponent(t)}/sendMessage`, CT_JSON, { chat_id: p.chat_id, text: p.text })
    case 'get_updates':  return jsonGet(`https://api.telegram.org/bot${encodeURIComponent(t)}/getUpdates`, {})
    default: return { ok: false, error: `telegram action inconnue: ${a}` }
  }
}
async function runTodoist(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_tasks':  return jsonGet('https://api.todoist.com/rest/v2/tasks', auth)
    case 'create_task': return jsonPost('https://api.todoist.com/rest/v2/tasks', auth, p)
    case 'close_task':  return jsonPost(`https://api.todoist.com/rest/v2/tasks/${p.id}/close`, auth, {})
    default: return { ok: false, error: `todoist action inconnue: ${a}` }
  }
}
async function runSpotify(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}` }
  const authJson = { ...auth, ...CT_JSON }
  switch (a) {
    case 'me':          return jsonGet('https://api.spotify.com/v1/me', auth)
    case 'search':      return jsonGet(`https://api.spotify.com/v1/search?type=track,album,artist&limit=10&q=${encodeURIComponent(String(p.q ?? ''))}`, auth)
    case 'play':        {
      const url = p.device_id ? `https://api.spotify.com/v1/me/player/play?device_id=${encodeURIComponent(String(p.device_id))}` : 'https://api.spotify.com/v1/me/player/play'
      const body = p.uris || p.context_uri ? JSON.stringify({ uris: p.uris, context_uri: p.context_uri }) : undefined
      const r = await fetch(url, { method: 'PUT', headers: body ? authJson : auth, body })
      return { ok: r.ok, output: r.ok ? 'lecture relancee' : `HTTP ${r.status}` }
    }
    case 'pause':       { const r = await fetch('https://api.spotify.com/v1/me/player/pause', { method: 'PUT', headers: auth }); return { ok: r.ok, output: r.ok ? 'pause' : `HTTP ${r.status}` } }
    case 'next':        { const r = await fetch('https://api.spotify.com/v1/me/player/next', { method: 'POST', headers: auth }); return { ok: r.ok, output: r.ok ? 'next' : `HTTP ${r.status}` } }
    case 'list_playlists': return jsonGet('https://api.spotify.com/v1/me/playlists?limit=30', auth)
    case 'list_devices':   return jsonGet('https://api.spotify.com/v1/me/player/devices', auth)
    case 'transfer_playback': {
      if (!p.device_id) return { ok: false, error: 'device_id requis (utilise list_devices d abord)' }
      const r = await fetch('https://api.spotify.com/v1/me/player', {
        method: 'PUT',
        headers: authJson,
        body: JSON.stringify({ device_ids: [p.device_id], play: p.play !== false }),
      })
      return { ok: r.ok, output: r.ok ? `playback bascule sur ${p.device_id}` : `HTTP ${r.status}` }
    }
    case 'set_volume': {
      const vol = Math.max(0, Math.min(100, Number(p.volume_percent ?? 50)))
      const url = p.device_id
        ? `https://api.spotify.com/v1/me/player/volume?volume_percent=${vol}&device_id=${encodeURIComponent(String(p.device_id))}`
        : `https://api.spotify.com/v1/me/player/volume?volume_percent=${vol}`
      const r = await fetch(url, { method: 'PUT', headers: auth })
      return { ok: r.ok, output: r.ok ? `volume ${vol}%` : `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `spotify action inconnue: ${a}` }
  }
}
async function runStabilityAI(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, Accept: 'application/json' }
  switch (a) {
    case 'generate_sd3': {
      // Stability multipart/form-data : prompt + aspect_ratio
      const form = new FormData()
      form.append('prompt', String(p.prompt ?? ''))
      form.append('aspect_ratio', String(p.aspect_ratio ?? '1:1'))
      form.append('output_format', 'png')
      const r = await fetch('https://api.stability.ai/v2beta/stable-image/generate/sd3', { method: 'POST', headers: auth, body: form })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'generate_ultra': {
      const form = new FormData()
      form.append('prompt', String(p.prompt ?? ''))
      form.append('output_format', 'png')
      const r = await fetch('https://api.stability.ai/v2beta/stable-image/generate/ultra', { method: 'POST', headers: auth, body: form })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'upscale': {
      const form = new FormData()
      // image_b64 must be passed as a Blob ; we just base64-decode in caller
      // For the LLM-driven planner this path is rare ; document it.
      form.append('image', String(p.image_b64 ?? ''))
      const r = await fetch('https://api.stability.ai/v2beta/stable-image/upscale/fast', { method: 'POST', headers: auth, body: form })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `stability_ai action inconnue: ${a}` }
  }
}
async function runMapbox(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const tk = encodeURIComponent(t)
  switch (a) {
    case 'geocode':    return jsonGet(`https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(String(p.q ?? ''))}.json?access_token=${tk}&limit=5`, {})
    case 'reverse':    return jsonGet(`https://api.mapbox.com/geocoding/v5/mapbox.places/${p.lon},${p.lat}.json?access_token=${tk}`, {})
    case 'directions': {
      const profile = String(p.profile ?? 'driving')
      const coords = Array.isArray(p.coords) ? (p.coords as Array<[number, number]>).map((c) => `${c[0]},${c[1]}`).join(';') : ''
      return jsonGet(`https://api.mapbox.com/directions/v5/mapbox/${profile}/${coords}?access_token=${tk}&geometries=geojson`, {})
    }
    default: return { ok: false, error: `mapbox action inconnue: ${a}` }
  }
}
async function runCoinGecko(a: string, p: Record<string, unknown>, _key: string): Promise<ConnectorRunResult> {
  // Pro key (when present) goes via x-cg-pro-api-key. For free public usage, no header.
  const headers: Record<string, string> = {}
  if (_key && _key !== 'n/a') headers['x-cg-pro-api-key'] = _key
  switch (a) {
    case 'simple_price': {
      const ids = Array.isArray(p.ids) ? (p.ids as string[]).join(',') : String(p.ids ?? 'bitcoin,ethereum')
      const vs = Array.isArray(p.vs_currencies) ? (p.vs_currencies as string[]).join(',') : String(p.vs_currencies ?? 'usd,eur')
      return jsonGet(`https://api.coingecko.com/api/v3/simple/price?ids=${encodeURIComponent(ids)}&vs_currencies=${encodeURIComponent(vs)}`, headers)
    }
    case 'market_chart': {
      const id = String(p.id ?? 'bitcoin')
      const vs = String(p.vs_currency ?? 'usd')
      const days = String(p.days ?? '7')
      return jsonGet(`https://api.coingecko.com/api/v3/coins/${id}/market_chart?vs_currency=${vs}&days=${days}`, headers)
    }
    case 'trending':  return jsonGet('https://api.coingecko.com/api/v3/search/trending', headers)
    case 'global':    return jsonGet('https://api.coingecko.com/api/v3/global', headers)
    default: return { ok: false, error: `coingecko action inconnue: ${a}` }
  }
}
async function runPolygon(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const tk = encodeURIComponent(t)
  switch (a) {
    case 'ticker_details': return jsonGet(`https://api.polygon.io/v3/reference/tickers/${p.ticker}?apiKey=${tk}`, {})
    case 'snapshot':       return jsonGet(`https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/${p.ticker}?apiKey=${tk}`, {})
    case 'aggregates':     return jsonGet(`https://api.polygon.io/v2/aggs/ticker/${p.ticker}/range/${p.multiplier ?? 1}/${p.timespan ?? 'day'}/${p.from}/${p.to}?adjusted=true&sort=asc&apiKey=${tk}`, {})
    case 'list_tickers':   return jsonGet(`https://api.polygon.io/v3/reference/tickers?market=${p.market ?? 'stocks'}&limit=${p.limit ?? 100}&apiKey=${tk}`, {})
    default: return { ok: false, error: `polygon action inconnue: ${a}` }
  }
}
async function runDatadog(a: string, p: Record<string, unknown>, combo: string, baseUrl?: string): Promise<ConnectorRunResult> {
  const [apiKey, appKey] = combo.split(':')
  if (!apiKey || !appKey) return { ok: false, error: 'format <api_key>:<app_key>' }
  const root = (baseUrl || 'https://api.datadoghq.com').replace(/\/$/, '')
  const auth = { 'DD-API-KEY': apiKey, 'DD-APPLICATION-KEY': appKey, Accept: 'application/json' }
  switch (a) {
    case 'query_metric': {
      const from = Number(p.from ?? Math.floor(Date.now() / 1000) - 3600)
      const to = Number(p.to ?? Math.floor(Date.now() / 1000))
      return jsonGet(`${root}/api/v1/query?from=${from}&to=${to}&query=${encodeURIComponent(String(p.query ?? ''))}`, auth)
    }
    case 'list_monitors': return jsonGet(`${root}/api/v1/monitor`, auth)
    case 'list_logs': {
      const body = {
        filter: { query: p.query ?? '*', from: p.from ?? 'now-1h', to: p.to ?? 'now' },
        page: { limit: Number(p.limit ?? 50) },
      }
      return jsonPost(`${root}/api/v2/logs/events/search`, { ...auth, ...CT_JSON }, body)
    }
    case 'create_event': {
      const body = { title: p.title, text: p.text, alert_type: p.alert_type ?? 'info', tags: p.tags ?? [] }
      return jsonPost(`${root}/api/v1/events`, { ...auth, ...CT_JSON }, body)
    }
    default: return { ok: false, error: `datadog action inconnue: ${a}` }
  }
}
async function runHabitica(a: string, p: Record<string, unknown>, combo: string): Promise<ConnectorRunResult> {
  const [userId, token] = combo.split(':')
  if (!userId || !token) return { ok: false, error: 'format <userId>:<apiToken>' }
  const auth = { 'x-api-user': userId, 'x-api-key': token, 'x-client': 'AuroraIA-Cowork', ...CT_JSON }
  switch (a) {
    case 'list_tasks':  return jsonGet('https://habitica.com/api/v3/tasks/user', auth)
    case 'create_task': return jsonPost('https://habitica.com/api/v3/tasks/user', auth, { type: p.type ?? 'todo', text: p.text, priority: p.priority ?? 1, notes: p.notes })
    case 'score_up': {
      const r = await fetch(`https://habitica.com/api/v3/tasks/${p.task_id}/score/up`, { method: 'POST', headers: auth })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'user_stats':  return jsonGet('https://habitica.com/api/v3/user', auth)
    default: return { ok: false, error: `habitica action inconnue: ${a}` }
  }
}
async function runAlgolia(a: string, p: Record<string, unknown>, combo: string, _workspaceId?: string): Promise<ConnectorRunResult> {
  const [appId, key] = combo.split(':')
  if (!appId || !key) return { ok: false, error: 'format <AppId>:<SearchApiKey>' }
  const auth = { 'X-Algolia-Application-Id': appId, 'X-Algolia-API-Key': key, ...CT_JSON }
  const root = `https://${appId}-dsn.algolia.net/1`
  switch (a) {
    case 'search':       return jsonPost(`${root}/indexes/${encodeURIComponent(String(p.indexName ?? ''))}/query`, auth, { query: String(p.query ?? '') })
    case 'list_indexes': return jsonGet(`${root}/indexes`, auth)
    case 'browse':       return jsonGet(`${root}/indexes/${encodeURIComponent(String(p.indexName ?? ''))}/browse?hitsPerPage=${p.hitsPerPage ?? 100}`, auth)
    default: return { ok: false, error: `algolia action inconnue: ${a}` }
  }
}
async function runSendgrid(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'send': {
      const body = {
        personalizations: [{ to: [{ email: String(p.to ?? '') }] }],
        from: { email: String(p.from ?? '') },
        subject: String(p.subject ?? ''),
        content: [{ type: 'text/plain', value: String(p.content ?? p.text ?? '') }],
      }
      const r = await fetch('https://api.sendgrid.com/v3/mail/send', { method: 'POST', headers: auth, body: JSON.stringify(body) })
      // SendGrid renvoie 202 sans body en cas de succes
      if (r.ok) return { ok: true, output: 'mail accepte (202)' }
      const txt = await r.text()
      return { ok: false, error: `HTTP ${r.status}: ${txt.slice(0, 200)}` }
    }
    case 'list_templates': return jsonGet('https://api.sendgrid.com/v3/templates?generations=dynamic&page_size=20', { Authorization: `Bearer ${t}` })
    default: return { ok: false, error: `sendgrid action inconnue: ${a}` }
  }
}
async function runPinecone(a: string, p: Record<string, unknown>, t: string, host?: string): Promise<ConnectorRunResult> {
  if (!host) return { ok: false, error: 'baseUrl (host de l index) requis' }
  const root = host.replace(/\/$/, '')
  const auth = { 'Api-Key': t, ...CT_JSON }
  switch (a) {
    case 'list_indexes':       return jsonGet('https://api.pinecone.io/indexes', auth)
    case 'describe_index_stats': return jsonPost(`${root}/describe_index_stats`, auth, {})
    case 'query':              return jsonPost(`${root}/query`, auth, { vector: p.vector, topK: p.topK ?? 10, includeMetadata: true, filter: p.filter })
    case 'upsert':             return jsonPost(`${root}/vectors/upsert`, auth, { vectors: p.vectors })
    case 'delete': {
      const body = p.ids ? { ids: p.ids } : p.filter ? { filter: p.filter } : { deleteAll: true }
      return jsonPost(`${root}/vectors/delete`, auth, body)
    }
    default: return { ok: false, error: `pinecone action inconnue: ${a}` }
  }
}
async function runMailchimp(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const dc = (t.split('-')[1] || 'us1').trim()
  const root = `https://${dc}.api.mailchimp.com/3.0`
  const auth = { Authorization: `apikey ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_audiences':  return jsonGet(`${root}/lists?count=20`, { Authorization: `apikey ${t}` })
    case 'add_member':      return jsonPost(`${root}/lists/${p.list_id}/members`, auth, { email_address: p.email, status: p.status ?? 'subscribed', merge_fields: p.merge_fields })
    case 'list_campaigns':  return jsonGet(`${root}/campaigns?count=20`, { Authorization: `apikey ${t}` })
    case 'send_campaign': {
      const r = await fetch(`${root}/campaigns/${p.id}/actions/send`, { method: 'POST', headers: auth })
      return { ok: r.ok, output: r.ok ? 'campagne envoyee' : `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `mailchimp action inconnue: ${a}` }
  }
}
async function runAuth0(a: string, p: Record<string, unknown>, t: string, tenantBaseUrl?: string): Promise<ConnectorRunResult> {
  const base = (tenantBaseUrl || '').replace(/\/$/, '')
  if (!base) return { ok: false, error: 'baseUrl tenant Auth0 requis' }
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_users':  return jsonGet(`${base}/api/v2/users?per_page=20${p.q ? `&q=${encodeURIComponent(String(p.q))}` : ''}`, auth)
    case 'get_user':    return jsonGet(`${base}/api/v2/users/${encodeURIComponent(String(p.id ?? ''))}`, auth)
    case 'create_user': return jsonPost(`${base}/api/v2/users`, auth, p)
    case 'list_roles':  return jsonGet(`${base}/api/v2/roles`, auth)
    default: return { ok: false, error: `auth0 action inconnue: ${a}` }
  }
}
async function runMqtt(a: string, p: Record<string, unknown>, creds: string, broker?: string): Promise<ConnectorRunResult> {
  if (!broker) return { ok: false, error: 'baseUrl broker requis' }
  const { getBridgeUrl } = await import('../utils/runtime')
  const url = `${getBridgeUrl()}/api/cowork/iot/mqtt`
  switch (a) {
    case 'publish':       return jsonPost(url, CT_JSON, { broker, auth: creds, operation: 'publish', topic: p.topic, payload: p.payload, qos: p.qos ?? 0, retain: !!p.retain })
    case 'subscribe_once':return jsonPost(url, CT_JSON, { broker, auth: creds, operation: 'subscribe_once', topic: p.topic, timeout: p.timeout ?? 10 })
    default: return { ok: false, error: `mqtt action inconnue: ${a}` }
  }
}
async function runTuya(a: string, p: Record<string, unknown>, combo: string, baseUrl?: string): Promise<ConnectorRunResult> {
  // Tuya requires getting a token first then using it with HMAC sig per request.
  // To keep this implementation simple, we delegate to bridge for full HMAC flow.
  const { getBridgeUrl } = await import('../utils/runtime')
  return jsonPost(`${getBridgeUrl()}/api/cowork/iot/tuya`, CT_JSON, { creds: combo, baseUrl, operation: a, ...p })
}
async function runTado(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}` }
  switch (a) {
    case 'list_homes':  return jsonGet('https://my.tado.com/api/v2/me', auth)
    case 'list_zones':  return jsonGet(`https://my.tado.com/api/v2/homes/${p.home_id}/zones`, auth)
    case 'zone_state':  return jsonGet(`https://my.tado.com/api/v2/homes/${p.home_id}/zones/${p.zone_id}/state`, auth)
    case 'set_temperature': {
      const body = {
        setting: { type: 'HEATING', power: 'ON', temperature: { celsius: Number(p.temperature ?? 20) } },
        termination: { type: p.termination ?? 'MANUAL' },
      }
      const r = await fetch(`https://my.tado.com/api/v2/homes/${p.home_id}/zones/${p.zone_id}/overlay`, {
        method: 'PUT',
        headers: { ...auth, ...CT_JSON },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `tado action inconnue: ${a}` }
  }
}
async function runCircleCI(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { 'Circle-Token': t }
  switch (a) {
    case 'list_projects':  return jsonGet('https://circleci.com/api/v2/me/collaborations', auth)
    case 'list_pipelines': return jsonGet(`https://circleci.com/api/v2/project/${encodeURIComponent(String(p.project_slug ?? ''))}/pipeline`, auth)
    case 'get_pipeline':   return jsonGet(`https://circleci.com/api/v2/pipeline/${p.pipeline_id}`, auth)
    case 'list_jobs':      return jsonGet(`https://circleci.com/api/v2/workflow/${p.workflow_id}/job`, auth)
    case 'rerun_workflow': {
      const r = await fetch(`https://circleci.com/api/v2/workflow/${p.workflow_id}/rerun`, { method: 'POST', headers: auth })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `circleci action inconnue: ${a}` }
  }
}
// === v14 runs ===
async function runWyze(a: string, p: Record<string, unknown>, combo: string, _baseUrl?: string): Promise<ConnectorRunResult> {
  const [apikey, keyid] = (combo || '').split(':')
  if (!apikey || !keyid) return { ok: false, error: 'format requis: <apikey>:<keyid>' }
  const headers = { ...CT_JSON, apikey, keyid }
  const root = 'https://api.wyzecam.com'
  switch (a) {
    case 'list_devices': return jsonPost(`${root}/app/v2/home_page/get_object_list`, headers, { phone_id: 'aurora-ai' })
    case 'snapshot':     return jsonPost(`${root}/app/v2/device/get_capture_url`, headers, { phone_id: 'aurora-ai', device_mac: p.device_mac })
    case 'turn_on_plug':
    case 'turn_off_plug': {
      const action_value = a === 'turn_on_plug' ? 1 : 0
      return jsonPost(`${root}/app/v2/auto/run_action_list`, headers, { phone_id: 'aurora-ai', action_list: [{ action_key: 'set_state', instance_id: p.device_mac, action_params: { value: action_value } }] })
    }
    case 'get_events':   return jsonPost(`${root}/app/v2/device/get_event_list`, headers, { phone_id: 'aurora-ai', count: p.count ?? 20 })
    default: return { ok: false, error: `wyze action inconnue: ${a}` }
  }
}
async function runNodeRED(a: string, p: Record<string, unknown>, t: string, base?: string): Promise<ConnectorRunResult> {
  const root = (base ?? 'http://127.0.0.1:1880').replace(/\/+$/, '')
  const headers: Record<string, string> = { ...CT_JSON }
  if (t) headers.Authorization = `Bearer ${t}`
  switch (a) {
    case 'trigger_webhook': {
      const ep = String(p.endpoint ?? '/aurora-trigger').replace(/^([^/])/, '/$1')
      const body = (p.payload && typeof p.payload === 'object') ? p.payload : {}
      const r = await fetch(`${root}${ep}`, { method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(15_000) })
      const txt = await r.text().catch(() => '')
      return r.ok ? { ok: true, output: `webhook ${ep} -> 2xx`, data: { status: r.status, body: txt.slice(0, 500) } }
                  : { ok: false, error: `HTTP ${r.status}` }
    }
    case 'list_flows':     return jsonGet(`${root}/flows`, headers)
    case 'inject_message': {
      const id = String(p.id ?? '')
      if (!id) return { ok: false, error: 'inject.id requis' }
      const r = await fetch(`${root}/inject/${encodeURIComponent(id)}`, { method: 'POST', headers })
      return r.ok ? { ok: true, output: `inject ${id} declenche` } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `nodered action inconnue: ${a}` }
  }
}
async function runBambu(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  const root = 'https://api.bambulab.com/v1/iot-service/api'
  switch (a) {
    case 'list_printers':     return jsonGet(`${root}/user/bind`, auth)
    case 'get_printer_status':return jsonGet(`${root}/user/print/status?dev_id=${encodeURIComponent(String(p.dev_id ?? ''))}`, auth)
    case 'list_jobs':         return jsonGet(`${root}/user/print/list?limit=${p.limit ?? 20}`, auth)
    case 'pause_print':       return jsonPost(`${root}/user/print/control`, auth, { dev_id: p.dev_id, command: 'pause' })
    case 'resume_print':      return jsonPost(`${root}/user/print/control`, auth, { dev_id: p.dev_id, command: 'resume' })
    case 'cancel_print':      return jsonPost(`${root}/user/print/control`, auth, { dev_id: p.dev_id, command: 'stop' })
    default: return { ok: false, error: `bambu action inconnue: ${a}` }
  }
}
async function runStrava(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}` }
  const root = 'https://www.strava.com/api/v3'
  switch (a) {
    case 'get_athlete':      return jsonGet(`${root}/athlete`, auth)
    case 'list_activities':  return jsonGet(`${root}/athlete/activities?per_page=${p.per_page ?? 20}${p.after ? `&after=${p.after}` : ''}`, auth)
    case 'get_activity':     return jsonGet(`${root}/activities/${encodeURIComponent(String(p.id ?? ''))}`, auth)
    case 'get_stats': {
      const me = await jsonGet(`${root}/athlete`, auth) as ConnectorRunResult & { data?: { id?: number } }
      const id = me?.data?.id
      if (!id) return { ok: false, error: 'impossible de recuperer athleteId' }
      return jsonGet(`${root}/athletes/${id}/stats`, auth)
    }
    case 'list_segments':    return jsonGet(`${root}/segments/starred?per_page=${p.per_page ?? 30}`, auth)
    default: return { ok: false, error: `strava action inconnue: ${a}` }
  }
}
// === v15 runs ===
async function runTrello(a: string, p: Record<string, unknown>, combo: string): Promise<ConnectorRunResult> {
  const [key, token] = (combo || '').split(':')
  if (!key || !token) return { ok: false, error: 'format requis: <KEY>:<TOKEN>' }
  const qs = `key=${encodeURIComponent(key)}&token=${encodeURIComponent(token)}`
  const root = 'https://api.trello.com/1'
  switch (a) {
    case 'list_boards': return jsonGet(`${root}/members/me/boards?${qs}`, {})
    case 'list_lists':  return jsonGet(`${root}/boards/${encodeURIComponent(String(p.idBoard ?? ''))}/lists?${qs}`, {})
    case 'list_cards':  return jsonGet(`${root}/lists/${encodeURIComponent(String(p.idList ?? ''))}/cards?${qs}`, {})
    case 'create_card': {
      const params = new URLSearchParams({ key, token, idList: String(p.idList ?? ''), name: String(p.name ?? '') })
      if (p.desc) params.set('desc', String(p.desc))
      if (p.due) params.set('due', String(p.due))
      const r = await fetch(`${root}/cards?${params}`, { method: 'POST' })
      const d = await r.json()
      return r.ok ? { ok: true, data: d } : { ok: false, error: `HTTP ${r.status}` }
    }
    case 'move_card': {
      const r = await fetch(`${root}/cards/${encodeURIComponent(String(p.idCard ?? ''))}?${qs}&idList=${encodeURIComponent(String(p.idList ?? ''))}`, { method: 'PUT' })
      const d = await r.json()
      return r.ok ? { ok: true, data: d } : { ok: false, error: `HTTP ${r.status}` }
    }
    case 'archive_card': {
      const r = await fetch(`${root}/cards/${encodeURIComponent(String(p.idCard ?? ''))}?${qs}&closed=true`, { method: 'PUT' })
      return r.ok ? { ok: true, output: 'card archivee' } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `trello action inconnue: ${a}` }
  }
}
async function runJira(a: string, p: Record<string, unknown>, combo: string, base?: string): Promise<ConnectorRunResult> {
  if (!base) return { ok: false, error: 'baseUrl Jira requis (https://<workspace>.atlassian.net)' }
  const [email, token] = (combo || '').split(':')
  if (!email || !token) return { ok: false, error: 'format requis: <email>:<TOKEN>' }
  const auth = { Authorization: 'Basic ' + btoa(`${email}:${token}`), Accept: 'application/json', ...CT_JSON }
  const root = base.replace(/\/+$/, '') + '/rest/api/3'
  switch (a) {
    case 'jql_search': {
      const jql = encodeURIComponent(String(p.jql ?? 'order by updated DESC'))
      return jsonGet(`${root}/search?jql=${jql}&maxResults=${p.maxResults ?? 20}`, auth)
    }
    case 'get_issue':  return jsonGet(`${root}/issue/${encodeURIComponent(String(p.key ?? ''))}`, auth)
    case 'create_issue': return jsonPost(`${root}/issue`, auth, {
      fields: {
        project: { key: p.projectKey },
        summary: p.summary,
        issuetype: { name: p.issueType ?? 'Task' },
        description: p.description ? { type: 'doc', version: 1, content: [{ type: 'paragraph', content: [{ type: 'text', text: String(p.description) }] }] } : undefined,
      },
    })
    case 'add_comment': return jsonPost(`${root}/issue/${encodeURIComponent(String(p.key ?? ''))}/comment`, auth, {
      body: { type: 'doc', version: 1, content: [{ type: 'paragraph', content: [{ type: 'text', text: String(p.body ?? '') }] }] },
    })
    case 'list_transitions': return jsonGet(`${root}/issue/${encodeURIComponent(String(p.key ?? ''))}/transitions`, auth)
    case 'transition_issue': return jsonPost(`${root}/issue/${encodeURIComponent(String(p.key ?? ''))}/transitions`, auth, {
      transition: { id: String(p.transitionId) },
    })
    default: return { ok: false, error: `jira action inconnue: ${a}` }
  }
}
async function runWakaTime(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: 'Basic ' + btoa(`${t}:`) }
  const root = 'https://wakatime.com/api/v1'
  switch (a) {
    case 'get_user':       return jsonGet(`${root}/users/current`, auth)
    case 'get_stats':      return jsonGet(`${root}/users/current/stats/${encodeURIComponent(String(p.range ?? 'last_7_days'))}`, auth)
    case 'list_projects':  return jsonGet(`${root}/users/current/projects`, auth)
    case 'get_project_stats': return jsonGet(`${root}/users/current/projects/${encodeURIComponent(String(p.project ?? ''))}/${encodeURIComponent(String(p.range ?? 'last_7_days'))}`, auth)
    case 'list_summaries': {
      const start = String(p.start ?? new Date(Date.now() - 7 * 86_400_000).toISOString().slice(0, 10))
      const end = String(p.end ?? new Date().toISOString().slice(0, 10))
      return jsonGet(`${root}/users/current/summaries?start=${start}&end=${end}`, auth)
    }
    default: return { ok: false, error: `wakatime action inconnue: ${a}` }
  }
}
async function runPlex(a: string, p: Record<string, unknown>, t: string, base?: string): Promise<ConnectorRunResult> {
  const root = (base ?? 'http://127.0.0.1:32400').replace(/\/+$/, '')
  const headers = { 'X-Plex-Token': t, Accept: 'application/json' }
  switch (a) {
    case 'list_libraries': return jsonGet(`${root}/library/sections`, headers)
    case 'search':         return jsonGet(`${root}/search?query=${encodeURIComponent(String(p.q ?? ''))}`, headers)
    case 'list_recently_added': return jsonGet(`${root}/library/sections/${encodeURIComponent(String(p.section ?? '1'))}/recentlyAdded`, headers)
    case 'list_sessions':  return jsonGet(`${root}/status/sessions`, headers)
    case 'scan_section': {
      const r = await fetch(`${root}/library/sections/${encodeURIComponent(String(p.section ?? '1'))}/refresh`, { headers })
      return r.ok ? { ok: true, output: 'scan lance' } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `plex action inconnue: ${a}` }
  }
}
// === v16 runs ===
async function runGrafana(a: string, p: Record<string, unknown>, t: string, base?: string): Promise<ConnectorRunResult> {
  const root = (base ?? 'http://127.0.0.1:3000').replace(/\/+$/, '')
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_dashboards':   return jsonGet(`${root}/api/search?type=dash-db${p.query ? `&query=${encodeURIComponent(String(p.query))}` : ''}&limit=30`, auth)
    case 'get_dashboard':     return jsonGet(`${root}/api/dashboards/uid/${encodeURIComponent(String(p.uid ?? ''))}`, auth)
    case 'list_alerts':       return jsonGet(`${root}/api/alertmanager/grafana/api/v2/alerts`, auth)
    case 'list_datasources':  return jsonGet(`${root}/api/datasources`, auth)
    case 'query_datasource': {
      const dsUid = String(p.datasource_uid ?? '')
      if (!dsUid) return { ok: false, error: 'query_datasource.datasource_uid requis' }
      const expr = String(p.expr ?? '')
      const range = p.range && typeof p.range === 'object' ? p.range as { from?: string; to?: string } : { from: 'now-1h', to: 'now' }
      return jsonPost(`${root}/api/ds/query`, auth, {
        queries: [{ refId: 'A', datasource: { uid: dsUid }, expr, range: { from: range.from ?? 'now-1h', to: range.to ?? 'now' } }],
        from: range.from ?? 'now-1h', to: range.to ?? 'now',
      })
    }
    default: return { ok: false, error: `grafana action inconnue: ${a}` }
  }
}
// === v18 runs ===
async function runToggl(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: 'Basic ' + btoa(`${t}:api_token`), ...CT_JSON }
  const root = 'https://api.track.toggl.com/api/v9'
  switch (a) {
    case 'get_me':           return jsonGet(`${root}/me`, auth)
    case 'list_projects':    return jsonGet(`${root}/workspaces/${encodeURIComponent(String(p.workspace_id ?? ''))}/projects`, auth)
    case 'list_time_entries': {
      const start = String(p.start_date ?? new Date(Date.now() - 7 * 86_400_000).toISOString())
      const end = String(p.end_date ?? new Date().toISOString())
      return jsonGet(`${root}/me/time_entries?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`, auth)
    }
    case 'start_timer':      return jsonPost(`${root}/workspaces/${encodeURIComponent(String(p.workspace_id ?? ''))}/time_entries`, auth, {
      created_with: 'AuroraIA',
      description: p.description ?? '',
      project_id: p.project_id ?? null,
      duration: -1,  // Toggl convention : negative duration = running
      start: new Date().toISOString(),
      workspace_id: Number(p.workspace_id),
    })
    case 'get_current_timer':return jsonGet(`${root}/me/time_entries/current`, auth)
    case 'stop_current_timer': {
      const cur = await jsonGet(`${root}/me/time_entries/current`, auth) as ConnectorRunResult & { data?: { id?: number; workspace_id?: number } }
      if (!cur.ok || !cur.data?.id || !cur.data?.workspace_id) {
        return { ok: false, error: 'aucun timer en cours' }
      }
      const r = await fetch(`${root}/workspaces/${cur.data.workspace_id}/time_entries/${cur.data.id}/stop`, { method: 'PATCH', headers: auth })
      const d = r.ok ? await r.json() : null
      return r.ok ? { ok: true, data: d } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `toggl action inconnue: ${a}` }
  }
}
async function runMakeCom(a: string, p: Record<string, unknown>, url: string): Promise<ConnectorRunResult> {
  if (!url || !/^https:\/\/hook\./.test(url)) {
    return { ok: false, error: 'webhook URL Make.com manquante / invalide' }
  }
  switch (a) {
    case 'trigger': {
      const r = await fetch(url, {
        method: 'POST',
        headers: CT_JSON,
        body: JSON.stringify(p.payload && typeof p.payload === 'object' ? p.payload : p),
        signal: AbortSignal.timeout(20_000),
      })
      const txt = await r.text().catch(() => '')
      return r.ok
        ? { ok: true, output: `webhook trigger OK : ${txt.slice(0, 200)}`, data: { status: r.status, body: txt.slice(0, 1000) } }
        : { ok: false, error: `HTTP ${r.status}: ${txt.slice(0, 200)}` }
    }
    case 'trigger_get': {
      const params = p.params && typeof p.params === 'object' ? p.params as Record<string, unknown> : {}
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) qs.set(k, String(v))
      const full = qs.toString() ? `${url}?${qs}` : url
      const r = await fetch(full, { method: 'GET', signal: AbortSignal.timeout(20_000) })
      const txt = await r.text().catch(() => '')
      return r.ok
        ? { ok: true, output: `GET webhook OK : ${txt.slice(0, 200)}`, data: { status: r.status, body: txt.slice(0, 1000) } }
        : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `make_com action inconnue: ${a}` }
  }
}

async function runHubSpot(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  const root = 'https://api.hubapi.com/crm/v3'
  switch (a) {
    case 'list_contacts': return jsonGet(`${root}/objects/contacts?limit=${p.limit ?? 20}&properties=firstname,lastname,email,phone,createdate`, auth)
    case 'get_contact':   return jsonGet(`${root}/objects/contacts/${encodeURIComponent(String(p.id ?? ''))}?properties=firstname,lastname,email,phone,company`, auth)
    case 'create_contact': return jsonPost(`${root}/objects/contacts`, auth, {
      properties: { email: p.email, firstname: p.firstname, lastname: p.lastname, phone: p.phone },
    })
    case 'list_deals':   return jsonGet(`${root}/objects/deals?limit=${p.limit ?? 20}&properties=dealname,amount,dealstage,closedate,createdate`, auth)
    case 'create_deal':  return jsonPost(`${root}/objects/deals`, auth, {
      properties: { dealname: p.dealname, amount: String(p.amount ?? 0), dealstage: p.dealstage ?? 'qualifiedtobuy' },
    })
    case 'add_note_to_contact': {
      // 1. Create note. 2. Associate with contact.
      const note = await jsonPost(`${root}/objects/notes`, auth, {
        properties: { hs_note_body: p.body, hs_timestamp: Date.now() },
      }) as ConnectorRunResult & { data?: { id?: string } }
      if (!note.ok || !note.data?.id) return { ok: false, error: 'note creation failed' }
      const r = await fetch(`${root}/objects/notes/${note.data.id}/associations/contacts/${encodeURIComponent(String(p.contactId))}/note_to_contact`, {
        method: 'PUT', headers: auth,
      })
      return r.ok ? { ok: true, output: `note ${note.data.id} associee au contact ${p.contactId}` } : { ok: false, error: `HTTP ${r.status}` }
    }
    default: return { ok: false, error: `hubspot action inconnue: ${a}` }
  }
}
async function runClerk(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_users':  return jsonGet(`https://api.clerk.com/v1/users?limit=${p.limit ?? 20}${p.query ? `&query=${encodeURIComponent(String(p.query))}` : ''}`, auth)
    case 'get_user':    return jsonGet(`https://api.clerk.com/v1/users/${encodeURIComponent(String(p.id ?? ''))}`, auth)
    case 'list_orgs':   return jsonGet('https://api.clerk.com/v1/organizations?limit=20', auth)
    case 'ban_user':    return jsonPost(`https://api.clerk.com/v1/users/${p.id}/ban`, auth, {})
    default: return { ok: false, error: `clerk action inconnue: ${a}` }
  }
}
async function runCloudinary(a: string, p: Record<string, unknown>, combo: string): Promise<ConnectorRunResult> {
  const [cloud, key, secret] = combo.split(':')
  if (!cloud || !key || !secret) return { ok: false, error: 'format <CloudName>:<ApiKey>:<ApiSecret>' }
  const auth = { Authorization: 'Basic ' + btoa(`${key}:${secret}`) }
  switch (a) {
    case 'list_resources': return jsonGet(`https://api.cloudinary.com/v1_1/${cloud}/resources/image?max_results=${p.max_results ?? 50}`, auth)
    case 'usage':          return jsonGet(`https://api.cloudinary.com/v1_1/${cloud}/usage`, auth)
    case 'transform_url': {
      // Build a delivery URL with transformations applied client-side (no API call).
      const t = String(p.transformations ?? 'w_400,c_fill,q_auto,f_auto')
      const publicId = String(p.public_id ?? '')
      const url = `https://res.cloudinary.com/${cloud}/image/upload/${t}/${publicId}`
      return { ok: true, output: url, data: { url } }
    }
    default: return { ok: false, error: `cloudinary action inconnue: ${a}` }
  }
}
async function runSentry(a: string, p: Record<string, unknown>, t: string, defaultOrg?: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, Accept: 'application/json' }
  const org = String(p.org ?? defaultOrg ?? '')
  switch (a) {
    case 'list_projects': return jsonGet('https://sentry.io/api/0/projects/', auth)
    case 'list_issues':   return jsonGet(`https://sentry.io/api/0/projects/${org}/${p.project}/issues/`, auth)
    case 'get_issue':     return jsonGet(`https://sentry.io/api/0/issues/${p.issue_id}/`, auth)
    case 'resolve_issue': {
      const r = await fetch(`https://sentry.io/api/0/issues/${p.issue_id}/`, {
        method: 'PUT',
        headers: { ...auth, ...CT_JSON },
        body: JSON.stringify({ status: 'resolved' }),
      })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `sentry action inconnue: ${a}` }
  }
}
async function runPerplexity(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'chat':
    case 'sonar': {
      const messages = p.messages ?? [{ role: 'user', content: String(p.prompt ?? p.q ?? '') }]
      return jsonPost('https://api.perplexity.ai/chat/completions', auth, {
        model: p.model || (a === 'sonar' ? 'sonar' : 'sonar-pro'),
        messages,
        return_citations: true,
      })
    }
    default: return { ok: false, error: `perplexity action inconnue: ${a}` }
  }
}
async function runAppleReminders(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  // Le connecteur Apple Reminders fonctionne en pushant une commande sur la
  // file mobile que le raccourci iOS poll. Il execute "Add new Reminder"
  // (ou "Find Reminders") cote iOS et POST le resultat.
  try {
    const { getBridgeUrl } = await import('../utils/runtime')
    const root = getBridgeUrl()
    const dispatchResp = await fetch(`${root}/api/cowork/mobile/dispatch`, {
      method: 'POST',
      headers: CT_JSON,
      body: JSON.stringify({
        kind: a === 'create_reminder' ? 'create_reminder' : 'list_reminders',
        payload: p,
      }),
    })
    const d = await dispatchResp.json() as { ok: boolean; commandId?: string; error?: string }
    if (!d.ok || !d.commandId) return { ok: false, error: d.error || 'dispatch mobile a echoue' }
    return { ok: true, output: `commande pushee au raccourci iOS (${d.commandId}). Le tel doit poller pour l executer.`, data: { commandId: d.commandId } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}
async function runYouTube(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  switch (a) {
    case 'search':         return jsonGet(`https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=10&q=${encodeURIComponent(String(p.q ?? ''))}&key=${encodeURIComponent(t)}`, {})
    case 'video_details':  return jsonGet(`https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=${encodeURIComponent(String(p.id ?? ''))}&key=${encodeURIComponent(t)}`, {})
    default: return { ok: false, error: `youtube action inconnue: ${a}` }
  }
}
async function runHomeAssistant(a: string, p: Record<string, unknown>, t: string, baseUrl?: string): Promise<ConnectorRunResult> {
  const root = (baseUrl || 'http://homeassistant.local:8123').replace(/\/$/, '')
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_states':  return jsonGet(`${root}/api/states`, auth)
    case 'get_state':    return jsonGet(`${root}/api/states/${p.entity_id}`, auth)
    case 'call_service': return jsonPost(`${root}/api/services/${p.domain}/${p.service}`, auth, p.data ?? {})
    default: return { ok: false, error: `home_assistant action inconnue: ${a}` }
  }
}
async function runOpenWeather(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const q = String(p.q ?? p.city ?? 'Paris')
  switch (a) {
    case 'current':   return jsonGet(`https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(q)}&units=metric&lang=fr&appid=${encodeURIComponent(t)}`, {})
    case 'forecast':  return jsonGet(`https://api.openweathermap.org/data/2.5/forecast?q=${encodeURIComponent(q)}&units=metric&lang=fr&appid=${encodeURIComponent(t)}`, {})
    default: return { ok: false, error: `openweather action inconnue: ${a}` }
  }
}
async function runDeepL(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const baseUrl = t.endsWith(':fx') ? 'https://api-free.deepl.com/v2' : 'https://api.deepl.com/v2'
  const auth = { Authorization: `DeepL-Auth-Key ${t}`, 'Content-Type': 'application/x-www-form-urlencoded' }
  switch (a) {
    case 'translate': {
      const body = new URLSearchParams({ text: String(p.text ?? ''), target_lang: String(p.target_lang ?? 'EN').toUpperCase() })
      const r = await fetch(`${baseUrl}/translate`, { method: 'POST', headers: auth, body: body.toString() })
      const d = await r.json() as { translations?: Array<{ text: string }> }
      return { ok: r.ok, data: d, output: d.translations?.[0]?.text }
    }
    case 'usage': return jsonGet(`${baseUrl}/usage`, { Authorization: `DeepL-Auth-Key ${t}` })
    default: return { ok: false, error: `deepl action inconnue: ${a}` }
  }
}
async function runWikipedia(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  const lang = String(p.lang ?? 'fr')
  switch (a) {
    case 'search':  return jsonGet(`https://${lang}.wikipedia.org/w/api.php?action=opensearch&format=json&search=${encodeURIComponent(String(p.q ?? ''))}&limit=10&origin=*`, {})
    case 'extract': return jsonGet(`https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(String(p.title ?? ''))}`, {})
    default: return { ok: false, error: `wikipedia action inconnue: ${a}` }
  }
}
async function runArxiv(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  if (a !== 'search') return { ok: false, error: `arxiv action inconnue: ${a}` }
  const url = `http://export.arxiv.org/api/query?search_query=${encodeURIComponent(String(p.query ?? ''))}&max_results=${Number(p.max_results ?? 10)}`
  const r = await fetch(url, { signal: AbortSignal.timeout(15_000) })
  const txt = await r.text()
  return { ok: r.ok, output: txt.slice(0, 5000) }
}
async function runHN(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  switch (a) {
    case 'top':    return jsonGet('https://hacker-news.firebaseio.com/v0/topstories.json', {})
    case 'search': return jsonGet(`https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(String(p.q ?? ''))}&hitsPerPage=10`, {})
    default: return { ok: false, error: `hackernews action inconnue: ${a}` }
  }
}
async function runReddit(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  switch (a) {
    case 'list_subreddit': return jsonGet(`https://www.reddit.com/r/${encodeURIComponent(String(p.subreddit ?? 'all'))}/${p.sort ?? 'hot'}.json?limit=20`, { 'User-Agent': 'AuroraIA' })
    case 'search':         return jsonGet(`https://www.reddit.com/search.json?q=${encodeURIComponent(String(p.q ?? ''))}&limit=20`, { 'User-Agent': 'AuroraIA' })
    default: return { ok: false, error: `reddit action inconnue: ${a}` }
  }
}
async function runHF(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'search_models': return jsonGet(`https://huggingface.co/api/models?search=${encodeURIComponent(String(p.search ?? ''))}&limit=10`, {})
    case 'inference':     return jsonPost(`https://api-inference.huggingface.co/models/${encodeURIComponent(String(p.model ?? ''))}`, auth, { inputs: p.inputs })
    default: return { ok: false, error: `huggingface action inconnue: ${a}` }
  }
}
async function runReplicate(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Token ${t}`, ...CT_JSON }
  switch (a) {
    case 'list_models':       return jsonGet('https://api.replicate.com/v1/models', auth)
    case 'create_prediction': return jsonPost('https://api.replicate.com/v1/predictions', auth, { version: p.version, input: p.input })
    default: return { ok: false, error: `replicate action inconnue: ${a}` }
  }
}
async function runHorde(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { apikey: t, ...CT_JSON }
  switch (a) {
    case 'generate_async': return jsonPost('https://stablehorde.net/api/v2/generate/async', auth, { prompt: p.prompt, params: p.params ?? { width: 512, height: 512 } })
    case 'check_status':   return jsonGet(`https://stablehorde.net/api/v2/generate/check/${p.id}`, {})
    default: return { ok: false, error: `stable_horde action inconnue: ${a}` }
  }
}
async function runPostgres(a: string, p: Record<string, unknown>, dsn: string): Promise<ConnectorRunResult> {
  const { getBridgeUrl } = await import('../utils/runtime')
  const url = `${getBridgeUrl()}/api/cowork/db/sql`
  switch (a) {
    case 'query':
    case 'exec':  return jsonPost(url, CT_JSON, { dsn, sql: p.sql, args: p.args ?? [], allowWrite: a === 'exec' })
    case 'tables': return jsonPost(url, CT_JSON, { dsn, sql: "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name", args: [] })
    default: return { ok: false, error: `postgres action inconnue: ${a}` }
  }
}
async function runRedisUpstash(a: string, p: Record<string, unknown>, t: string, baseUrl?: string): Promise<ConnectorRunResult> {
  if (!baseUrl) return { ok: false, error: 'baseUrl Upstash requise' }
  const root = baseUrl.replace(/\/$/, '')
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  // Upstash REST: POST avec un array commande+args
  const cmd = (() => {
    switch (a) {
      case 'get':  return ['GET', String(p.key ?? '')]
      case 'set':  return ['SET', String(p.key ?? ''), String(p.value ?? '')]
      case 'del':  return ['DEL', String(p.key ?? '')]
      case 'keys': return ['KEYS', String(p.pattern ?? '*')]
      case 'incr': return ['INCR', String(p.key ?? '')]
      default: return null
    }
  })()
  if (!cmd) return { ok: false, error: `redis_upstash action inconnue: ${a}` }
  return jsonPost(root, auth, cmd)
}
async function runS3(a: string, p: Record<string, unknown>, creds: string, endpoint?: string): Promise<ConnectorRunResult> {
  const { getBridgeUrl } = await import('../utils/runtime')
  const url = `${getBridgeUrl()}/api/cowork/storage/s3`
  return jsonPost(url, CT_JSON, { creds, endpoint: endpoint || 'https://s3.amazonaws.com', operation: a, ...p })
}
async function runTailscale(a: string, p: Record<string, unknown>, t: string, tailnet?: string): Promise<ConnectorRunResult> {
  const tn = tailnet || '-'
  const auth = { Authorization: `Bearer ${t}` }
  switch (a) {
    case 'list_devices': return jsonGet(`https://api.tailscale.com/api/v2/tailnet/${encodeURIComponent(tn)}/devices`, auth)
    case 'get_device':   return jsonGet(`https://api.tailscale.com/api/v2/device/${p.device_id}`, auth)
    case 'list_keys':    return jsonGet(`https://api.tailscale.com/api/v2/tailnet/${encodeURIComponent(tn)}/keys`, auth)
    default: return { ok: false, error: `tailscale action inconnue: ${a}` }
  }
}
async function runPlausible(a: string, p: Record<string, unknown>, apiKey: string, siteId?: string): Promise<ConnectorRunResult> {
  if (!siteId) return { ok: false, error: 'site_id requis (workspaceId, ex: example.com)' }
  const auth = { Authorization: `Bearer ${apiKey}` }
  const sid = encodeURIComponent(siteId)
  switch (a) {
    case 'aggregate': return jsonGet(`https://plausible.io/api/v1/stats/aggregate?site_id=${sid}&period=${p.period ?? '7d'}&metrics=${p.metrics ?? 'visitors,pageviews,bounce_rate,visit_duration'}`, auth)
    case 'breakdown': return jsonGet(`https://plausible.io/api/v1/stats/breakdown?site_id=${sid}&period=${p.period ?? '7d'}&property=${p.property ?? 'event:page'}&limit=${p.limit ?? 20}`, auth)
    case 'realtime':  return jsonGet(`https://plausible.io/api/v1/stats/realtime/visitors?site_id=${sid}`, auth)
    default: return { ok: false, error: `plausible action inconnue: ${a}` }
  }
}
async function runPushover(a: string, p: Record<string, unknown>, combo: string): Promise<ConnectorRunResult> {
  const [appToken, userKey] = combo.split(':')
  if (!appToken || !userKey) return { ok: false, error: 'format attendu: <app_token>:<user_key>' }
  if (a !== 'notify') return { ok: false, error: `pushover action inconnue: ${a}` }
  const body = new URLSearchParams({
    token: appToken,
    user: userKey,
    message: String(p.message ?? ''),
    title: p.title ? String(p.title) : '',
    priority: p.priority ? String(p.priority) : '0',
    url: p.url ? String(p.url) : '',
    sound: p.sound ? String(p.sound) : '',
  })
  const r = await fetch('https://api.pushover.net/1/messages.json', { method: 'POST', body })
  const d = await r.json() as { status: number; errors?: string[] }
  return d.status === 1 ? { ok: true, output: 'notif envoyee' } : { ok: false, error: (d.errors || []).join(', ') || 'echec' }
}
async function runTwilio(a: string, p: Record<string, unknown>, combo: string, fromNumber?: string): Promise<ConnectorRunResult> {
  const [sid, token] = combo.split(':')
  if (!sid || !token) return { ok: false, error: 'format attendu: <Account SID>:<Auth Token>' }
  const auth = { Authorization: 'Basic ' + btoa(`${sid}:${token}`) }
  const url = `https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`
  const callUrl = `https://api.twilio.com/2010-04-01/Accounts/${sid}/Calls.json`
  switch (a) {
    case 'send_sms': {
      const body = new URLSearchParams({ To: String(p.to ?? ''), From: fromNumber || String(p.from ?? ''), Body: String(p.body ?? '') })
      const r = await fetch(url, { method: 'POST', headers: auth, body })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'send_whatsapp': {
      const body = new URLSearchParams({ To: `whatsapp:${p.to}`, From: `whatsapp:${fromNumber || p.from}`, Body: String(p.body ?? '') })
      const r = await fetch(url, { method: 'POST', headers: auth, body })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'make_call': {
      const body = new URLSearchParams({ To: String(p.to ?? ''), From: fromNumber || String(p.from ?? ''), Url: String(p.url ?? '') })
      const r = await fetch(callUrl, { method: 'POST', headers: auth, body })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `twilio action inconnue: ${a}` }
  }
}
async function runOSM(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  const ua = { 'User-Agent': 'AuroraIA/Cowork (mailto:user@local)' }
  switch (a) {
    case 'search':  return jsonGet(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&q=${encodeURIComponent(String(p.q ?? ''))}`, ua)
    case 'reverse': return jsonGet(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${p.lat}&lon=${p.lon}`, ua)
    default: return { ok: false, error: `openstreetmap action inconnue: ${a}` }
  }
}
async function runHIBP(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { 'hibp-api-key': t, 'User-Agent': 'AuroraIA-Cowork' }
  switch (a) {
    case 'breached_account':
      return jsonGet(`https://haveibeenpwned.com/api/v3/breachedaccount/${encodeURIComponent(String(p.email ?? ''))}?truncateResponse=false`, auth)
    case 'all_breaches':
      return jsonGet('https://haveibeenpwned.com/api/v3/breaches', auth)
    case 'pwned_password': {
      // k-anonymity : send first 5 chars of SHA1 hash, locally compare suffix
      const password = String(p.password ?? '')
      if (!password) return { ok: false, error: 'password manquant' }
      // Compute SHA-1 with WebCrypto
      const data = new TextEncoder().encode(password)
      const hashBuf = await crypto.subtle.digest('SHA-1', data)
      const hex = Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, '0').toUpperCase()).join('')
      const prefix = hex.slice(0, 5)
      const suffix = hex.slice(5)
      const r = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`, { signal: AbortSignal.timeout(10_000) })
      if (!r.ok) return { ok: false, error: `HTTP ${r.status}` }
      const txt = await r.text()
      const match = txt.split('\n').find((line) => line.toUpperCase().startsWith(suffix))
      if (match) {
        const count = match.split(':')[1]?.trim() ?? '?'
        return { ok: true, output: `compromis ${count} fois`, data: { pwned: true, count: Number(count) || 0 } }
      }
      return { ok: true, output: 'jamais vu dans une fuite', data: { pwned: false } }
    }
    default: return { ok: false, error: `hibp action inconnue: ${a}` }
  }
}
async function runAbuseIPDB(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Key: t, Accept: 'application/json' }
  switch (a) {
    case 'check':     return jsonGet(`https://api.abuseipdb.com/api/v2/check?ipAddress=${encodeURIComponent(String(p.ip ?? ''))}&maxAgeInDays=${p.maxAgeInDays ?? 90}`, auth)
    case 'blacklist': return jsonGet(`https://api.abuseipdb.com/api/v2/blacklist?confidenceMinimum=${p.confidence ?? 75}&limit=${p.limit ?? 100}`, auth)
    case 'report': {
      const body = new URLSearchParams({ ip: String(p.ip ?? ''), categories: String(p.categories ?? '14'), comment: String(p.comment ?? '') })
      const r = await fetch('https://api.abuseipdb.com/api/v2/report', { method: 'POST', headers: { ...auth, 'Content-Type': 'application/x-www-form-urlencoded' }, body })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `abuseipdb action inconnue: ${a}` }
  }
}
async function runDiscogs(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Discogs token=${t}`, 'User-Agent': 'AuroraIA-Cowork/1.0' }
  switch (a) {
    case 'search':  return jsonGet(`https://api.discogs.com/database/search?q=${encodeURIComponent(String(p.q ?? ''))}&type=${p.type ?? 'release'}&per_page=10`, auth)
    case 'release': return jsonGet(`https://api.discogs.com/releases/${p.id}`, auth)
    case 'artist':  return jsonGet(`https://api.discogs.com/artists/${p.id}/releases?per_page=20`, auth)
    default: return { ok: false, error: `discogs action inconnue: ${a}` }
  }
}
async function runIGDB(a: string, p: Record<string, unknown>, combo: string): Promise<ConnectorRunResult> {
  const [clientId, bearer] = combo.split(':')
  if (!clientId || !bearer) return { ok: false, error: 'format <client_id>:<bearer>' }
  const auth = { 'Client-ID': clientId, Authorization: `Bearer ${bearer}`, Accept: 'application/json' }
  switch (a) {
    case 'search_games': {
      const limit = Number(p.limit ?? 10)
      const body = `search "${String(p.q ?? '').replace(/"/g, '\\"')}"; fields name,summary,first_release_date,rating,url; limit ${limit};`
      return jsonPost('https://api.igdb.com/v4/games', auth, undefined as never).catch(async () => {
        // jsonPost JSON-encodes; IGDB expects raw text. Manual fetch:
        const r = await fetch('https://api.igdb.com/v4/games', { method: 'POST', headers: auth, body })
        const d = await r.json()
        return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
      })
    }
    case 'top_rated': {
      const r = await fetch('https://api.igdb.com/v4/games', { method: 'POST', headers: auth, body: 'fields name,rating,url; sort rating desc; where rating > 90; limit 20;' })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    case 'platforms': {
      const r = await fetch('https://api.igdb.com/v4/platforms', { method: 'POST', headers: auth, body: 'fields name,abbreviation; limit 50;' })
      const d = await r.json()
      return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 200) }
    }
    default: return { ok: false, error: `igdb action inconnue: ${a}` }
  }
}
async function runOpenLibrary(a: string, p: Record<string, unknown>): Promise<ConnectorRunResult> {
  switch (a) {
    case 'search': return jsonGet(`https://openlibrary.org/search.json?q=${encodeURIComponent(String(p.q ?? ''))}&limit=10`, {})
    case 'book':   return jsonGet(`https://openlibrary.org/isbn/${encodeURIComponent(String(p.isbn ?? ''))}.json`, {})
    case 'author': return jsonGet(`https://openlibrary.org/authors/${encodeURIComponent(String(p.id ?? ''))}/works.json?limit=20`, {})
    default: return { ok: false, error: `openlibrary action inconnue: ${a}` }
  }
}

async function runMeshy(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'me':                return jsonGet('https://api.meshy.ai/openapi/v2/text-to-3d?page_num=1&page_size=1', auth)
    case 'text_to_3d':        return jsonPost('https://api.meshy.ai/openapi/v2/text-to-3d', auth, { mode: p.mode || 'preview', prompt: p.prompt, art_style: p.art_style || 'realistic', negative_prompt: p.negative_prompt })
    case 'text_to_3d_status': return jsonGet(`https://api.meshy.ai/openapi/v2/text-to-3d/${p.id}`, auth)
    case 'image_to_3d':       return jsonPost('https://api.meshy.ai/openapi/v1/image-to-3d', auth, { image_url: p.image_url, enable_pbr: p.enable_pbr ?? true })
    case 'text_to_texture':   return jsonPost('https://api.meshy.ai/openapi/v1/text-to-texture', auth, { model_url: p.model_url, object_prompt: p.object_prompt, style_prompt: p.style_prompt })
    default: return { ok: false, error: `meshy action inconnue: ${a}` }
  }
}
async function runBrave(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { 'X-Subscription-Token': t, Accept: 'application/json' }
  switch (a) {
    case 'web':  return jsonGet(`https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(String(p.q ?? ''))}&count=10`, auth)
    case 'news': return jsonGet(`https://api.search.brave.com/res/v1/news/search?q=${encodeURIComponent(String(p.q ?? ''))}&count=10`, auth)
    default: return { ok: false, error: `brave_search action inconnue: ${a}` }
  }
}
async function runFigma(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { 'X-Figma-Token': t }
  switch (a) {
    case 'me':            return jsonGet('https://api.figma.com/v1/me', auth)
    case 'get_file':      return jsonGet(`https://api.figma.com/v1/files/${p.file_key}`, auth)
    case 'list_comments': return jsonGet(`https://api.figma.com/v1/files/${p.file_key}/comments`, auth)
    default: return { ok: false, error: `figma action inconnue: ${a}` }
  }
}
async function runStripe(a: string, _p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}` }
  switch (a) {
    case 'list_customers':     return jsonGet('https://api.stripe.com/v1/customers?limit=20', auth)
    case 'list_charges':       return jsonGet('https://api.stripe.com/v1/charges?limit=20', auth)
    case 'list_subscriptions': return jsonGet('https://api.stripe.com/v1/subscriptions?limit=20', auth)
    default: return { ok: false, error: `stripe action inconnue: ${a}` }
  }
}
async function runOpenAI(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'chat':  return jsonPost('https://api.openai.com/v1/chat/completions', auth, { model: p.model || 'gpt-4o-mini', messages: p.messages ?? [{ role: 'user', content: String(p.prompt ?? '') }], temperature: p.temperature ?? 0.7 })
    case 'embed': return jsonPost('https://api.openai.com/v1/embeddings', auth, { model: p.model || 'text-embedding-3-small', input: p.input })
    default: return { ok: false, error: `openai action inconnue: ${a}` }
  }
}
async function runAnthropic(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { 'x-api-key': t, 'anthropic-version': '2023-06-01', ...CT_JSON }
  switch (a) {
    case 'chat': return jsonPost('https://api.anthropic.com/v1/messages', auth, { model: p.model || 'claude-sonnet-4-6', max_tokens: p.max_tokens || 1024, messages: p.messages ?? [{ role: 'user', content: String(p.prompt ?? '') }] })
    default: return { ok: false, error: `anthropic action inconnue: ${a}` }
  }
}
async function runMistral(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'chat': return jsonPost('https://api.mistral.ai/v1/chat/completions', auth, { model: p.model || 'mistral-large-latest', messages: p.messages ?? [{ role: 'user', content: String(p.prompt ?? '') }] })
    default: return { ok: false, error: `mistral action inconnue: ${a}` }
  }
}
async function runGroq(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'chat': return jsonPost('https://api.groq.com/openai/v1/chat/completions', auth, { model: p.model || 'llama-3.3-70b-versatile', messages: p.messages ?? [{ role: 'user', content: String(p.prompt ?? '') }] })
    default: return { ok: false, error: `groq action inconnue: ${a}` }
  }
}
async function runOpenRouter(a: string, p: Record<string, unknown>, t: string): Promise<ConnectorRunResult> {
  const auth = { Authorization: `Bearer ${t}`, ...CT_JSON }
  switch (a) {
    case 'chat':         return jsonPost('https://openrouter.ai/api/v1/chat/completions', auth, { model: p.model || 'openai/gpt-4o-mini', messages: p.messages ?? [{ role: 'user', content: String(p.prompt ?? '') }] })
    case 'list_models':  return jsonGet('https://openrouter.ai/api/v1/models', auth)
    default: return { ok: false, error: `openrouter action inconnue: ${a}` }
  }
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function jsonGet(url: string, headers: Record<string, string>): Promise<ConnectorRunResult> {
  const r = await fetch(url, { headers, signal: AbortSignal.timeout(15_000) })
  const ct = r.headers.get('content-type') || ''
  if (/json/.test(ct)) {
    const d = await r.json()
    return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 400) }
  }
  const txt = await r.text()
  return { ok: r.ok, output: txt.slice(0, 5000), error: r.ok ? undefined : txt.slice(0, 400) }
}

async function jsonPost(url: string, headers: Record<string, string>, body: unknown): Promise<ConnectorRunResult> {
  const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(20_000) })
  const ct = r.headers.get('content-type') || ''
  if (/json/.test(ct)) {
    const d = await r.json()
    return { ok: r.ok, data: d, error: r.ok ? undefined : JSON.stringify(d).slice(0, 400) }
  }
  const txt = await r.text()
  return { ok: r.ok, output: txt.slice(0, 5000), error: r.ok ? undefined : txt.slice(0, 400) }
}
