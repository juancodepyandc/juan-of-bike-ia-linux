/**
 * modulePipelineStages.ts — Standard multi-stage pipeline definitions for all Aurora modules.
 *
 * Architecture Contract:
 * Every module follows the 4-macro-phase lifecycle:
 *   1. ANALYSE (0% - 25%)      : Intention, Cadrage, Storyboard, Preflight, Références
 *   2. REALISATION (25% - 70%)  : Génération, Synthèse, Cuisson, Inférence, Rendu, Compilation
 *   3. VERIFICATION (70% - 90%) : Validation, Tests, Sandbox, Juge de vision, Contrôle qualité
 *   4. FINALISATION (90% - 100%): Packaging, Post-traitement, Export livrable, Métadonnées
 */

export interface SubStageDefinition {
  key: string
  label: string
  pctStart: number
  pctEnd: number
  detailTemplate?: string
}

export interface MacroStageDefinition {
  key: "analyse" | "realisation" | "verification" | "finalisation"
  label: string
  pctStart: number
  pctEnd: number
  description: string
  subStages: SubStageDefinition[]
}

export type ModuleName =
  | "code"
  | "3d"
  | "video"
  | "voix"
  | "image"
  | "cowork"
  | "cyber"
  | "conversation"
  | "manga"
  | "academy"

export const MODULE_PIPELINE_STAGES: Record<ModuleName, MacroStageDefinition[]> = {
  code: [
    {
      key: "analyse",
      label: "Analyse & Cadrage",
      pctStart: 0,
      pctEnd: 25,
      description: "Classification d intention, analyse des directives et preflight local",
      subStages: [
        { key: "intent", label: "Classification d intention", pctStart: 0, pctEnd: 8 },
        { key: "preflight", label: "Preflight & environnement", pctStart: 8, pctEnd: 16 },
        { key: "architecture_plan", label: "Plan d architecture structure", pctStart: 16, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Génération Agentique",
      pctStart: 25,
      pctEnd: 70,
      description: "Génération des fichiers de code WS3 et intégration des assets",
      subStages: [
        { key: "intermodule_assets", label: "Assets inter-modules", pctStart: 25, pctEnd: 35 },
        { key: "agentic_generation", label: "Production de code multi-fichiers", pctStart: 35, pctEnd: 62 },
        { key: "missing_modules", label: "Résolution des dépendances & imports", pctStart: 62, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Sandbox & Qualité",
      pctStart: 70,
      pctEnd: 90,
      description: "Validation sandbox, tests, portes de qualité et boucle de correction",
      subStages: [
        { key: "sandbox_execution", label: "Exécution & tests sandbox", pctStart: 70, pctEnd: 78 },
        { key: "quality_gates", label: "Portes de qualité & fidélité", pctStart: 78, pctEnd: 84 },
        { key: "auto_correction", label: "Auto-réparation & régression", pctStart: 84, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Packaging & Livraison",
      pctStart: 90,
      pctEnd: 100,
      description: "Génération support, manifest et validation de conformité finale",
      subStages: [
        { key: "support_files", label: "Fichiers support & README", pctStart: 90, pctEnd: 95 },
        { key: "delivery_manifest", label: "Livrable validé & archivage", pctStart: 95, pctEnd: 100 },
      ],
    },
  ],

  "3d": [
    {
      key: "analyse",
      label: "Analyse & Concept",
      pctStart: 0,
      pctEnd: 20,
      description: "Compréhension de la forme 3D et synthèse des vues de référence",
      subStages: [
        { key: "prompt_concept", label: "Analyse du concept", pctStart: 0, pctEnd: 10 },
        { key: "reference_synth", label: "Génération multi-vues FLUX", pctStart: 10, pctEnd: 20 },
      ],
    },
    {
      key: "realisation",
      label: "Génération 3D & PBR",
      pctStart: 20,
      pctEnd: 70,
      description: "Reconstruction maillage, retopologie et cuisson des matériaux PBR",
      subStages: [
        { key: "mesh_generation", label: "Génération maillage Hunyuan3D/Trellis", pctStart: 20, pctEnd: 45 },
        { key: "retopology_uv", label: "Retopologie & dépliage UV", pctStart: 45, pctEnd: 58 },
        { key: "pbr_materials", label: "Textures PBR & Normal maps", pctStart: 58, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Contrôle Qualité & Juge IA",
      pctStart: 70,
      pctEnd: 90,
      description: "Vérification étanchéité (watertight), audit visuel et score géométrique",
      subStages: [
        { key: "watertight_check", label: "Vérification étanchéité & normales", pctStart: 70, pctEnd: 78 },
        { key: "vision_judge", label: "Juge IA vision & conformité", pctStart: 78, pctEnd: 85 },
        { key: "color_diagnostic", label: "Diagnostic couleur & texture", pctStart: 85, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Finalisation & Export GLB",
      pctStart: 90,
      pctEnd: 100,
      description: "Injection cinématique, rendu vignettes et export GLB canonique",
      subStages: [
        { key: "animation_injection", label: "Gréement & animation", pctStart: 90, pctEnd: 95 },
        { key: "glb_export", label: "Export GLB & métadonnées", pctStart: 95, pctEnd: 100 },
      ],
    },
  ],

  video: [
    {
      key: "analyse",
      label: "Analyse & Storyboard",
      pctStart: 0,
      pctEnd: 20,
      description: "Découpage des plans, keyframes FLUX et scénarisation",
      subStages: [
        { key: "storyboard_plan", label: "Scénarisation & découpage", pctStart: 0, pctEnd: 10 },
        { key: "keyframe_synth", label: "Keyframes & continuité visuelle", pctStart: 10, pctEnd: 20 },
      ],
    },
    {
      key: "realisation",
      label: "Rendu Vidéo & Audio",
      pctStart: 20,
      pctEnd: 70,
      description: "Diffusion Wan2.2/LTX, synthèse vocale et lipsync",
      subStages: [
        { key: "shot_diffusion", label: "Rendu des plans vidéo", pctStart: 20, pctEnd: 55 },
        { key: "audio_voice_synth", label: "Synthèse vocale & synchronisation", pctStart: 55, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Contrôle Qualité & Raccords",
      pctStart: 70,
      pctEnd: 85,
      description: "Contrôle des coutures de raccord, fluidité temporelle et audit esthétique",
      subStages: [
        { key: "aesthetic_judge", label: "Audit esthétique des plans", pctStart: 70, pctEnd: 78 },
        { key: "seam_consistency", label: "Continuité & transition", pctStart: 78, pctEnd: 85 },
      ],
    },
    {
      key: "finalisation",
      label: "Montage & Export Master",
      pctStart: 85,
      pctEnd: 100,
      description: "Upscaling Real-ESRGAN, assemblage MP4 et sous-titres",
      subStages: [
        { key: "video_upscale", label: "Suréchantillonnage HD/4K", pctStart: 85, pctEnd: 92 },
        { key: "assembly_export", label: "Concaténation finale & audio master", pctStart: 92, pctEnd: 100 },
      ],
    },
  ],

  voix: [
    {
      key: "analyse",
      label: "Analyse & Phonémisation",
      pctStart: 0,
      pctEnd: 25,
      description: "Segmentation du texte, phonémisation FR et analyse de prosodie",
      subStages: [
        { key: "text_segmentation", label: "Découpage & respiration", pctStart: 0, pctEnd: 12 },
        { key: "phonemization", label: "Phonémisation & prosodie", pctStart: 12, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Synthèse & Clonage",
      pctStart: 25,
      pctEnd: 70,
      description: "Inférence acoustique TTS, adaptation du timbre et génération vocale",
      subStages: [
        { key: "timbre_matching", label: "Clonage & profil vocal", pctStart: 25, pctEnd: 45 },
        { key: "audio_synthesis", label: "Synthèse vocale neuronale", pctStart: 45, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Contrôle Spectral",
      pctStart: 70,
      pctEnd: 90,
      description: "Contrôle de dynamique, clarté et absence d artefacts",
      subStages: [
        { key: "spectral_analysis", label: "Analyse fréquentielle", pctStart: 70, pctEnd: 80 },
        { key: "timing_alignment", label: "Vérification de cadence", pctStart: 80, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Masterisation & Export",
      pctStart: 90,
      pctEnd: 100,
      description: "Normalisation LUFS, masterisation et export WAV/MP3",
      subStages: [
        { key: "lufs_normalization", label: "Normalisation audio", pctStart: 90, pctEnd: 95 },
        { key: "audio_export", label: "Export profil & session", pctStart: 95, pctEnd: 100 },
      ],
    },
  ],

  image: [
    {
      key: "analyse",
      label: "Analyse & Composition",
      pctStart: 0,
      pctEnd: 20,
      description: "Règles de composition, cadrage et ratio d aspect",
      subStages: [
        { key: "composition_plan", label: "Cadrage & ratio", pctStart: 0, pctEnd: 10 },
        { key: "prompt_building", label: "Prompt esthétique & éclairage", pctStart: 10, pctEnd: 20 },
      ],
    },
    {
      key: "realisation",
      label: "Génération Visuelle",
      pctStart: 20,
      pctEnd: 70,
      description: "Débruitage latent FLUX/SDXL et passes de haute résolution",
      subStages: [
        { key: "diffusion_pass", label: "Diffusion latente principale", pctStart: 20, pctEnd: 55 },
        { key: "hi_res_refine", label: "Raffinement des détails", pctStart: 55, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Contrôle & Restauration",
      pctStart: 70,
      pctEnd: 90,
      description: "Restauration visage, détourage et contrôle qualité",
      subStages: [
        { key: "face_restore", label: "Restauration visage & mains", pctStart: 70, pctEnd: 80 },
        { key: "aesthetic_gate", label: "Contrôle de netteté & artefacts", pctStart: 80, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Export & Métadonnées",
      pctStart: 90,
      pctEnd: 100,
      description: "Export PNG/WebP haute fidélité et archivage",
      subStages: [
        { key: "format_export", label: "Génération livrable & métadonnées", pctStart: 90, pctEnd: 100 },
      ],
    },
  ],

  cowork: [
    {
      key: "analyse",
      label: "Cadrage & Clarification",
      pctStart: 0,
      pctEnd: 25,
      description: "Extraction du contexte, clarification et planification des actions",
      subStages: [
        { key: "context_digest", label: "Digestion du contexte & documents", pctStart: 0, pctEnd: 12 },
        { key: "plan_formulation", label: "Plan d exécution multi-étapes", pctStart: 12, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Recherche & Rédaction",
      pctStart: 25,
      pctEnd: 75,
      description: "Recherche web, navigation et synthèse documentaire",
      subStages: [
        { key: "web_research", label: "Recherche web & crawl", pctStart: 25, pctEnd: 50 },
        { key: "content_synthesis", label: "Synthèse & rédaction", pctStart: 50, pctEnd: 75 },
      ],
    },
    {
      key: "verification",
      label: "Revue & Cohérence",
      pctStart: 75,
      pctEnd: 90,
      description: "Vérification des assertions, cohérence et structure",
      subStages: [
        { key: "fact_checking", label: "Contrôle des sources & cohérence", pctStart: 75, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Livrable & Archivage",
      pctStart: 90,
      pctEnd: 100,
      description: "Mise en page, export documents et métadonnées",
      subStages: [
        { key: "document_export", label: "Génération document final", pctStart: 90, pctEnd: 100 },
      ],
    },
  ],

  cyber: [
    {
      key: "analyse",
      label: "Reconnaissance & Cibles",
      pctStart: 0,
      pctEnd: 25,
      description: "Cartographie de surface d attaque et inventaire",
      subStages: [
        { key: "target_discovery", label: "Découverte des cibles & ports", pctStart: 0, pctEnd: 15 },
        { key: "surface_mapping", label: "Cartographie des services", pctStart: 15, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Scan & Détection",
      pctStart: 25,
      pctEnd: 70,
      description: "Scan automatisé des vulnérabilités et configurations",
      subStages: [
        { key: "vuln_scan", label: "Scan automatisé des failles", pctStart: 25, pctEnd: 55 },
        { key: "config_audit", label: "Audit des configurations", pctStart: 55, pctEnd: 70 },
      ],
    },
    {
      key: "verification",
      label: "Validation des Failles",
      pctStart: 70,
      pctEnd: 90,
      description: "Tri des faux positifs et évaluation de criticité CVSS",
      subStages: [
        { key: "cvss_scoring", label: "Évaluation criticité & tri", pctStart: 70, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Rapport & Remédiation",
      pctStart: 90,
      pctEnd: 100,
      description: "Génération du rapport d audit et plan de remédiation",
      subStages: [
        { key: "report_generation", label: "Génération rapport d audit", pctStart: 90, pctEnd: 100 },
      ],
    },
  ],

  conversation: [
    {
      key: "analyse",
      label: "Compréhension",
      pctStart: 0,
      pctEnd: 25,
      description: "Analyse sémantique et mémoire conversationnelle",
      subStages: [
        { key: "intent_parsing", label: "Analyse du message", pctStart: 0, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Raisonnement & Réponse",
      pctStart: 25,
      pctEnd: 80,
      description: "Inférence LLM et appel des outils nécessaires",
      subStages: [
        { key: "model_inference", label: "Génération de la réponse", pctStart: 25, pctEnd: 80 },
      ],
    },
    {
      key: "verification",
      label: "Cohérence & Ton",
      pctStart: 80,
      pctEnd: 95,
      description: "Validation de la réponse et tonalité",
      subStages: [
        { key: "tone_check", label: "Validation de cohérence", pctStart: 80, pctEnd: 95 },
      ],
    },
    {
      key: "finalisation",
      label: "Restitution",
      pctStart: 95,
      pctEnd: 100,
      description: "Formatage et transmission du message",
      subStages: [
        { key: "message_delivery", label: "Affichage final", pctStart: 95, pctEnd: 100 },
      ],
    },
  ],

  manga: [
    {
      key: "analyse",
      label: "Scénario & Découpage",
      pctStart: 0,
      pctEnd: 25,
      description: "Découpage des cases, composition et dialogues",
      subStages: [
        { key: "script_breakdown", label: "Découpage des cases", pctStart: 0, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Dessin & Encrage",
      pctStart: 25,
      pctEnd: 75,
      description: "Génération des planches, tramage et bulles",
      subStages: [
        { key: "panel_drawing", label: "Génération des planches", pctStart: 25, pctEnd: 75 },
      ],
    },
    {
      key: "verification",
      label: "Contrôle & Raccord",
      pctStart: 75,
      pctEnd: 90,
      description: "Contrôle de continuité des personnages et lisibilité",
      subStages: [
        { key: "character_continuity", label: "Vérification des personnages", pctStart: 75, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Export Planches",
      pctStart: 90,
      pctEnd: 100,
      description: "Export haute résolution et livre numérique",
      subStages: [
        { key: "page_export", label: "Export HD", pctStart: 90, pctEnd: 100 },
      ],
    },
  ],

  academy: [
    {
      key: "analyse",
      label: "Analyse Pédagogique",
      pctStart: 0,
      pctEnd: 25,
      description: "Cadrage du programme et identification des notions clés",
      subStages: [
        { key: "syllabus_analysis", label: "Analyse des notions", pctStart: 0, pctEnd: 25 },
      ],
    },
    {
      key: "realisation",
      label: "Génération Cours & Quiz",
      pctStart: 25,
      pctEnd: 75,
      description: "Création des fiches de révision, cartes mémoire et exercices",
      subStages: [
        { key: "content_generation", label: "Production du contenu pédagogique", pctStart: 25, pctEnd: 75 },
      ],
    },
    {
      key: "verification",
      label: "Vérification des Notions",
      pctStart: 75,
      pctEnd: 90,
      description: "Contrôle d exactitude académique et clarté",
      subStages: [
        { key: "academic_accuracy", label: "Contrôle d exactitude", pctStart: 75, pctEnd: 90 },
      ],
    },
    {
      key: "finalisation",
      label: "Export Fiches & Anki",
      pctStart: 90,
      pctEnd: 100,
      description: "Export Anki, fiches PDF/HTML et métadonnées",
      subStages: [
        { key: "deck_export", label: "Export livrable", pctStart: 90, pctEnd: 100 },
      ],
    },
  ],
}

/**
 * Normalise any module string to its canonical key.
 */
export function getCanonicalModuleName(raw: string): ModuleName {
  const norm = (raw || "").toLowerCase().trim()
  if (norm === "3d" || norm === "three_d" || norm === "threed") return "3d"
  if (norm === "video" || norm === "cinema" || norm === "film") return "video"
  if (norm === "code" || norm === "coding" || norm === "coder") return "code"
  if (norm === "voix" || norm === "voice" || norm === "audio" || norm === "tts") return "voix"
  if (norm === "image" || norm === "images" || norm === "img") return "image"
  if (norm === "cowork") return "cowork"
  if (norm === "cyber" || norm === "security") return "cyber"
  if (norm === "manga") return "manga"
  if (norm === "academy" || norm === "learning") return "academy"
  return "conversation"
}
