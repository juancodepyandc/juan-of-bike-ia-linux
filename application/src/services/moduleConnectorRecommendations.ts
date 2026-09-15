/**
 * moduleConnectorRecommendations — per-module connector + Aurora extension hints.
 *
 * Purpose: tell the user, for each module, WHICH connectors and which Aurora
 * Connect Extension capabilities would unlock noticeably better results.
 *
 * The user explicitly asked: "Tu peux recommander pour chaque module un
 * connecteur a mettre et meme non connecter il peut utiliser aurora
 * extension si besoin pour aller chercher n importe quel information
 * possible pour avoir des meilleurs resultats."
 *
 * Each entry tells:
 *   - which connectors give the biggest quality jump
 *   - what extension capabilities to use even when no API key is set
 *   - what specifically gets better when each one is wired
 */

import type { ConnectorId } from './coworkSettings.ts'

export type ModuleId =
  | 'conversation'
  | 'image'
  | 'code'
  | 'video'
  | 'drawing'
  | '3d'
  | 'learning'
  | 'voice'
  | 'cyber'

export type ConnectorRecommendation = {
  id: ConnectorId
  reason: string
  /** Quality lift from "noticeable" to "transformative" */
  impact: 'transformative' | 'high' | 'medium'
  /** Optional fallback when the connector is not configured */
  fallbackHint?: string
}

export type ExtensionCapability = {
  capability: string
  description: string
  /** What part of the module benefits */
  benefits: string
}

export type ModuleConnectorPlan = {
  module: ModuleId
  /** Top-3 connectors that give the biggest result improvement on this module */
  primary: ConnectorRecommendation[]
  /** Optional connectors to add if the user has them */
  optional: ConnectorRecommendation[]
  /** Capabilities of the Aurora Connect browser extension that lift quality even without any API key */
  extensionFallback: ExtensionCapability[]
}

export const MODULE_CONNECTOR_PLAN: Record<ModuleId, ModuleConnectorPlan> = {
  '3d': {
    module: '3d',
    primary: [
      {
        id: 'huggingface',
        impact: 'transformative',
        reason:
          "Acces aux modeles Hunyuan3D-2.1 multivue et DreamGaussian (MIT) en haute precision : poids fp16 a la demande sans pull legacy, evite les fallbacks shape_only et debloque le mode 4-vues qui supprime ~70% des artefacts.",
        fallbackHint:
          "Sans token HF, Aurora utilise la cache locale et peut tomber en single-view: l'extension Aurora Connect peut malgre tout aller chercher les fiches techniques (GitHub README, model cards) pour calibrer les parametres.",
      },
      {
        id: 'meshy',
        impact: 'high',
        reason:
          'Meshy AI fournit un fallback texture+rig 3D rapide quand Hunyuan3D rate (mesh_quality_ok=false). Texture 2K avec UVs propres par defaut, GLB pret pour Three.js.',
      },
      {
        id: 'replicate',
        impact: 'high',
        reason:
          "Replicate sert d'arriere-garde pour TripoSR (rapide), CSM-3D (precision), ou Stable Video 3D quand l'utilisateur veut une rotation 360deg synthetique avant reconstruction multivue.",
      },
    ],
    optional: [
      {
        id: 'github',
        impact: 'medium',
        reason:
          'Permet de pousser le mesh genere directement dans un repo (release GLB) ou de cloner des templates Blender procedurals (kits gear/cable/linkage).',
      },
      {
        id: 'gdrive',
        impact: 'medium',
        reason:
          "Lecture/ecriture de bibliotheques de references HDRI et modeles GLB partages entre projets sans tout retelecharger.",
      },
      {
        id: 'huggingface',
        impact: 'medium',
        reason:
          "Acces additionnel aux datasets de poses (Mixamo retargeting, Pose Animator) pour enrichir le rigging Rigify.",
      },
    ],
    extensionFallback: [
      {
        capability: 'reference_visual_search',
        description:
          'Cherche des images de reference (Google Images, GIS) du sujet exact et les rapatrie pour conditionner FLUX et Hunyuan3D multivue.',
        benefits:
          "Permet a Aurora de generer un objet identifiable meme sans le pousser dans le prompt: le mesh ressemble vraiment au sujet (ex: une marque, un personnage connu, un produit precis).",
      },
      {
        capability: 'spec_sheet_grab',
        description:
          'Recupere les fiches techniques HTML (Wikipedia, sites constructeurs) pour fixer les dimensions et proportions reelles.',
        benefits:
          'Le mesh sort aux bonnes proportions sans hallucination — utile pour pieces mecaniques, vehicules, et produits tech.',
      },
      {
        capability: 'rigging_pose_lookup',
        description:
          'Trouve des references de poses anatomiques (skeleton diagrams, sports stills) pour guider l auto-rigging et les motion presets.',
        benefits:
          'Le rigging Rigify scale-to-mesh + IK donne des deformations propres, et les motion presets (marche, danse, applaudissement) deviennent realistes au lieu de mouvements raides.',
      },
      {
        capability: 'physics_law_lookup',
        description:
          'Cherche les lois physiques (gravite locale, frictions typiques, vitesses angulaires) qui s appliquent au sujet.',
        benefits:
          'Les templates physiques Blender (chaine, pendule, courroie) sortent avec des valeurs plausibles au lieu de defauts arbitraires.',
      },
    ],
  },

  code: {
    module: 'code',
    primary: [
      {
        id: 'github',
        impact: 'transformative',
        reason:
          "GitHub donne acces a la recherche de code, aux issues et releases, aux logs CI: Aurora peut lire des exemples reels avant de generer (ex: chercher 'three.js orbit controls boilerplate' renvoie du code sain) et detecter les bugs en regardant les issues du package importé.",
        fallbackHint:
          "Sans token, l extension Aurora Connect peut quand meme parser la page HTML d un repo public et extraire le README + arborescence.",
      },
      {
        id: 'huggingface',
        impact: 'high',
        reason:
          'Permet au module code de telecharger des assets ML (modeles, weights) pour des projets tels que demos transformers.js ou onnx-web — sinon le projet livre des stubs vides.',
      },
      {
        id: 'replicate',
        impact: 'high',
        reason:
          'Si le projet code livre par Aurora doit appeler un modele (image, audio, code), Replicate offre une API immediate sans avoir a heberger.',
      },
    ],
    optional: [
      {
        id: 'vercel',
        impact: 'medium',
        reason:
          "Aurora peut deployer le projet genere directement sur Vercel et fournir une URL live au user — utile pour landing pages et demos 3D.",
      },
      {
        id: 'netlify',
        impact: 'medium',
        reason:
          "Alternative au deploiement Vercel pour les sites statiques, jeux et applications PWA.",
      },
      {
        id: 'cloudflare',
        impact: 'medium',
        reason:
          "Workers + Pages pour deployer une edge API + frontend 3D en un seul push, ideal pour scenes Three.js servies a basse latence.",
      },
      {
        id: 'supabase',
        impact: 'medium',
        reason:
          "Si le projet genere un fullstack avec auth/db, Supabase est branche tout fait (Postgres + Auth + Storage) sans aucun setup serveur.",
      },
    ],
    extensionFallback: [
      {
        capability: 'documentation_fetch',
        description:
          "Lit la doc officielle (Three.js, React, Rapier, Vue, Tailwind, Vite, Next, Tauri) depuis le navigateur et extrait les API actuelles avant de generer.",
        benefits:
          "Empeche les hallucinations d API et les imports de fonctions disparues entre versions — les snippets generes compilent du premier coup.",
      },
      {
        capability: 'package_version_check',
        description:
          'Va lire npm/pypi/crates.io pour valider la version la plus recente stable de chaque dependance avant de l ecrire dans le manifeste.',
        benefits:
          'Evite les "package not found" en sandbox auto-correction et les warnings de deprecation.',
      },
      {
        capability: 'design_reference_grab',
        description:
          'Telecharge captures et palettes des landing pages premium (Awwwards, Lapa.ninja, Land-book) pour calibrer le visuel.',
        benefits:
          'Les sites generes sortent avec une qualite "Awwwards" plutot que template scolaire — palettes, typographies et compositions s alignent sur les references visuelles.',
      },
      {
        capability: 'github_issue_scan',
        description:
          'Recherche les issues recentes du package importe (ex: react-three/fiber + bug XYZ) pour detecter les pieges connus.',
        benefits:
          'Aurora ecrit du code qui evite les bugs ouverts au lieu de les reproduire.',
      },
      {
        capability: '3d_asset_search',
        description:
          'Cherche modeles GLB libres de droits (Sketchfab CC0, Polyhaven, KhronosGroup samples) pour qu une scene 3D soit livree avec de vrais meshes.',
        benefits:
          "Le projet genere n affiche plus 'cube par defaut' — il y a un GLB cohérent avec le sujet.",
      },
    ],
  },

  image: {
    module: 'image',
    primary: [
      {
        id: 'huggingface',
        impact: 'transformative',
        reason:
          'Acces aux poids FLUX-dev fp8, ControlNet, IP-Adapter et LoRAs specialises — l UI doit pouvoir tirer ces poids a la demande pour traiter les styles avances (anime, technical_render, cinematic).',
      },
      {
        id: 'stability_ai',
        impact: 'high',
        reason:
          'Stable Diffusion XL via API officielle pour les cas ou ComfyUI local est sature ou pour utiliser SDXL + refiner sans GPU.',
      },
      {
        id: 'replicate',
        impact: 'high',
        reason:
          'Replicate heberge des modeles tres specialises (PhotoMaker, IDM-VTON, FaceReplacer) qui ne tournent pas en local.',
      },
    ],
    optional: [
      {
        id: 'cloudinary',
        impact: 'medium',
        reason:
          'Stockage et transformations CDN pour les images generees — utile en mode multi-module quand l image est passee au module Code/Video.',
      },
      {
        id: 'figma',
        impact: 'medium',
        reason:
          'Export direct vers Figma pour les designers qui veulent integrer les visuels dans leurs maquettes.',
      },
    ],
    extensionFallback: [
      {
        capability: 'reference_visual_search',
        description:
          'Trouve des images-references du sujet pour conditionner FLUX (palette, framing, identity).',
        benefits:
          'Meilleure fidelite visuelle quand le prompt est ambigu ou quand le sujet est connu (marque, personnage).',
      },
      {
        capability: 'palette_extraction',
        description:
          "Extrait la palette dominante d'une page de reference (lookbook, brand guide) pour la transmettre au generationPrompt.",
        benefits:
          'Les images respectent une charte visuelle plutot que generer des couleurs aleatoires.',
      },
    ],
  },

  video: {
    module: 'video',
    primary: [
      {
        id: 'huggingface',
        impact: 'transformative',
        reason:
          'Wan2.2 T2V/I2V, Hunyuan-Video, AnimateDiff weights — l acces HF est central pour les bons modeles open source.',
      },
      {
        id: 'replicate',
        impact: 'high',
        reason:
          'Heberge des modeles I2V proprietaires (Kling, Runway Gen-3 quand expose) en cas de besoin de qualite cinema sans GPU.',
      },
      {
        id: 'stability_ai',
        impact: 'high',
        reason:
          "Stable Video Diffusion + Stable Video 3D pour des transitions image-to-video stables sans tuner local.",
      },
    ],
    optional: [
      {
        id: 'cloudinary',
        impact: 'medium',
        reason:
          'Stockage video + transcoding automatique (HLS, MP4 multi-bitrate) pour partage immediat depuis l app.',
      },
      {
        id: 'youtube',
        impact: 'medium',
        reason:
          "Upload direct des creations video sur YouTube depuis l UI.",
      },
    ],
    extensionFallback: [
      {
        capability: 'motion_reference_search',
        description:
          "Trouve des references de mouvement (clips ralentis, breakdowns animation) pour calibrer les motion presets I2V.",
        benefits:
          "Les animations 'marche', 'danse', 'parallaxe' deviennent fideles a une reference reelle au lieu d'etre interpretees au hasard.",
      },
      {
        capability: 'physics_law_lookup',
        description:
          "Recupere les vitesses, accelerations et trajectoires plausibles pour le sujet (chute libre, tir parabolique, course).",
        benefits:
          "L IA video respecte la physique — un objet qui tombe ralentit pas dans le vide, une voiture freine avec un realisme correct.",
      },
    ],
  },

  conversation: {
    module: 'conversation',
    primary: [
      {
        id: 'perplexity',
        impact: 'transformative',
        reason:
          "Pour les questions factuelles complexes, Perplexity fournit une recherche raisonnée temps reel — l'agent conversation gagne acces a l information actuelle (post-cutoff).",
      },
      {
        id: 'wikipedia',
        impact: 'high',
        reason:
          "Source factuelle gratuite et stable que l'agent peut citer. Idéal pour les questions historiques/factuelles.",
      },
      {
        id: 'github',
        impact: 'high',
        reason:
          'Quand la question concerne du code, github.code_search permet de pointer du vrai code et eviter les hallucinations.',
      },
    ],
    optional: [
      {
        id: 'gcal',
        impact: 'medium',
        reason:
          'Contexte calendrier permet de gerer les questions "que dois-je faire aujourd hui", "ai-je un meeting libre".',
      },
      {
        id: 'gmail',
        impact: 'medium',
        reason:
          'Lecture des derniers mails pour repondre aux questions "as-tu vu le mail de X" ou pour ecrire une reponse contextualisee.',
      },
      {
        id: 'notion',
        impact: 'medium',
        reason:
          "Acces aux notes Notion pour répondre dans le contexte des projets en cours.",
      },
    ],
    extensionFallback: [
      {
        capability: 'live_web_search',
        description:
          "Recherche temps reel via le navigateur si Perplexity n'est pas configure — extraction des 3-5 premiers résultats.",
        benefits:
          "L'agent peut citer des sources actuelles et eviter les hallucinations sur sujets post-cutoff.",
      },
      {
        capability: 'page_summary',
        description:
          'Demande au navigateur de resumer la page courante (article, page Wikipedia) pour repondre a "explique-moi cette page".',
        benefits:
          'Conversation contextualisee sur ce que le user lit a l instant, sans copier-coller manuel.',
      },
    ],
  },

  voice: {
    module: 'voice',
    primary: [
      {
        id: 'huggingface',
        impact: 'transformative',
        reason:
          'Voxtral-Small-24B-2507 (STT) + Kokoro-82M (TTS) sont sur HuggingFace — un token HF accelere les premieres preparations runtime et debloque les variantes voix multilingues.',
      },
      {
        id: 'spotify',
        impact: 'high',
        reason:
          "Permet a la voix copilote de jouer/changer/transferer de la musique en repondant 'mets du jazz dans le salon' avec Spotify Connect.",
      },
      {
        id: 'home_assistant',
        impact: 'high',
        reason:
          'Commande vocale lumieres / thermostats / scenes via Home Assistant. Transforme le copilote en vrai assistant maison.',
      },
    ],
    optional: [
      {
        id: 'philips_hue',
        impact: 'medium',
        reason:
          'Controle direct des lumieres Hue pour les commandes "tamise le salon" sans passer par HA.',
      },
      {
        id: 'gcal',
        impact: 'medium',
        reason:
          "Voix naturelle pour 'qu ai-je demain matin' / 'ajoute un evenement'.",
      },
    ],
    extensionFallback: [
      {
        capability: 'browser_tab_context',
        description:
          'Lit la page active du navigateur pour repondre vocalement a "lis-moi cet article" ou "resume cette page".',
        benefits:
          'Mode mains-libres immediat sans avoir a copier-coller du contenu.',
      },
      {
        capability: 'voice_search_actions',
        description:
          'Permet a la voix de declencher une recherche dans le navigateur ouvert ("recherche prix iphone 17").',
        benefits:
          "L'agent vocal n'est plus muet sur le web — il peut chercher et lire ce qu il trouve.",
      },
    ],
  },

  drawing: {
    module: 'drawing',
    primary: [
      {
        id: 'huggingface',
        impact: 'transformative',
        reason:
          'Acces aux LoRAs sketch-to-image specialises (Pixel Art XL, Lineart Anime XL) pour interpreter le croquis avec un style precis.',
      },
      {
        id: 'replicate',
        impact: 'high',
        reason:
          "Heberge ControlNet sketch + IP-Adapter pour des conversions sketch->image nettement plus fideles au trace que FLUX seul.",
      },
    ],
    optional: [
      {
        id: 'figma',
        impact: 'medium',
        reason:
          'Import direct de drawings depuis Figma comme reference pour FLUX.',
      },
    ],
    extensionFallback: [
      {
        capability: 'style_reference_grab',
        description:
          'Telecharge des references stylistiques (artiste, mouvement, palette) pour conditionner le rendu FLUX.',
        benefits:
          'Le sketch est interprete dans le style demande (manga 90s, watercolor moderne, brutaliste digital) sans avoir a tout decrire.',
      },
    ],
  },

  learning: {
    module: 'learning',
    primary: [
      {
        id: 'wikipedia',
        impact: 'transformative',
        reason:
          'Source factuelle pour generer cours et quiz precis sans hallucination, avec citations.',
      },
      {
        id: 'arxiv',
        impact: 'high',
        reason:
          'Pour les sujets scientifiques avances (math, physique, IA), arxiv permet de citer des papiers reels et de generer des quiz a partir des abstracts.',
      },
      {
        id: 'openlibrary',
        impact: 'high',
        reason:
          "Acces aux fiches livre + extraits pour generer cours litteraires et histoire avec sources verifiables.",
      },
    ],
    optional: [
      {
        id: 'anthropic',
        impact: 'medium',
        reason:
          "Quand l Ollama local sature, fallback Claude pour generer les quiz/cours longs.",
      },
      {
        id: 'huggingface',
        impact: 'medium',
        reason:
          "Datasets education (MMLU, HellaSwag) pour calibrer la difficulte des questions generees.",
      },
    ],
    extensionFallback: [
      {
        capability: 'syllabus_lookup',
        description:
          'Cherche des programmes officiels (BAC, college, university courses publics) pour caler la profondeur du cours.',
        benefits:
          'Le contenu genere correspond au niveau attendu (ex: terminale S vs licence L1).',
      },
      {
        capability: 'fact_check_loop',
        description:
          'Apres generation du quiz, le module verifie chaque reponse via une recherche rapide pour detecter les hallucinations.',
        benefits:
          'Quiz sans erreurs factuelles meme sur sujets pointus.',
      },
    ],
  },

  cyber: {
    module: 'cyber',
    primary: [
      {
        id: 'hibp',
        impact: 'transformative',
        reason:
          'HaveIBeenPwned permet de verifier les fuites de donnees connues — base de tout audit perso.',
      },
      {
        id: 'abuseipdb',
        impact: 'high',
        reason:
          'Verification IP malveillantes en temps reel pour analyser logs ou adresses suspectes.',
      },
      {
        id: 'github',
        impact: 'medium',
        reason:
          'Recherche de CVE et exploits documentes dans la base GitHub Advisory Database.',
      },
    ],
    optional: [
      {
        id: 'sentry',
        impact: 'medium',
        reason:
          'Lecture des erreurs Sentry pour correler les exceptions avec un audit de securite.',
      },
    ],
    extensionFallback: [
      {
        capability: 'cve_lookup',
        description:
          'Recherche les CVE recentes (NVD, Mitre, GitHub Advisories) pour le stack du user.',
        benefits:
          "Audit cyber a jour sans dependance API — l'extension parse les pages NVD et extrait les CVSS.",
      },
      {
        capability: 'osint_passive_recon',
        description:
          "Reconnaissance passive d'un domaine (dns, certs, archive.org snapshots) sans toucher a la cible.",
        benefits:
          'Audit passif respectueux de la legalite, parfait pour pentests autorises et bug bounty.',
      },
    ],
  },
}

/**
 * Return a flat list of recommendations to display in the module's
 * studio panel. Sorted: primary high-impact first, then optional.
 */
export function getModuleRecommendations(module: ModuleId): ModuleConnectorPlan {
  return MODULE_CONNECTOR_PLAN[module]
}

/**
 * Return the top connector for a module — used when only one badge fits.
 */
export function getTopConnectorRecommendation(module: ModuleId): ConnectorRecommendation | null {
  return MODULE_CONNECTOR_PLAN[module]?.primary[0] ?? null
}

/**
 * Build a markdown summary of all connectors recommended per module.
 * Used for the help panel and the README export.
 */
export function buildAllRecommendationsMarkdown(): string {
  const out: string[] = ['# Connecteurs et capacites Aurora Extension recommandes par module', '']
  for (const [moduleId, plan] of Object.entries(MODULE_CONNECTOR_PLAN)) {
    out.push(`## Module ${moduleId}`, '')
    out.push('### Connecteurs principaux (gros gain qualite)')
    for (const rec of plan.primary) {
      out.push(`- **${rec.id}** *(impact: ${rec.impact})* — ${rec.reason}`)
      if (rec.fallbackHint) out.push(`  - Fallback: ${rec.fallbackHint}`)
    }
    if (plan.optional.length > 0) {
      out.push('', '### Connecteurs optionnels (bonus)')
      for (const rec of plan.optional) {
        out.push(`- **${rec.id}** *(impact: ${rec.impact})* — ${rec.reason}`)
      }
    }
    out.push('', '### Aurora Connect Extension (sans aucune cle API)')
    for (const cap of plan.extensionFallback) {
      out.push(`- **${cap.capability}** — ${cap.description}`)
      out.push(`  - Benefice: ${cap.benefits}`)
    }
    out.push('')
  }
  return out.join('\n')
}
