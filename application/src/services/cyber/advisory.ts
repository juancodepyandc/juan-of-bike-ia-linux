export type CyberAdvisoryRequest = {
  model: string
  request: string
  target: string
  targetType: string
  isWeb: boolean
  stance: 'offense' | 'defense'
}

type GenerateAdvisory = (
  model: string,
  prompt: string,
  options: { num_ctx: number },
) => Promise<{ response?: string } | null | undefined>

export async function generateCyberAdvisory(input: CyberAdvisoryRequest, generate: GenerateAdvisory) {
  const prompt = `Prépare une analyse de sécurité défensive en français à partir des seules informations fournies.
Demande : ${JSON.stringify(input.request)}
Cible mentionnée : ${JSON.stringify(input.target)}
Type de cible déduit du texte : ${JSON.stringify(input.targetType)}
Angle : ${input.stance === 'offense' ? 'revue de robustesse dans un périmètre autorisé' : 'défense et durcissement'}.

Tu disposes uniquement de ce texte. Aucun outil n'a interrogé la cible ni collecté de télémétrie.
Distingue les éléments fournis, les hypothèses et les vérifications restant à effectuer.
Ne présente jamais une action proposée comme déjà exécutée, ni une vulnérabilité supposée comme constatée.
${input.isWeb
    ? 'Prépare les contrôles HTTP/TLS, authentification et configuration applicative pertinents, avec les preuves nécessaires pour conclure.'
    : 'Analyse les extraits et artefacts effectivement fournis. Indique les données manquantes pour confirmer le diagnostic.'}
Propose un plan de vérification autorisée et des correctifs défensifs adaptés.
Réponds en Markdown avec des conclusions proportionnées aux preuves disponibles.`

  const response = await generate(input.model, prompt, { num_ctx: 8192 })
  const content = (response?.response || '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .replace(/<think>[\s\S]*$/gi, '')
    .trim()
  if (!content) throw new Error('Aucune analyse exploitable reçue. Réessaie avec un modèle disponible.')
  return { content, basis: 'request_only' as const, targetVerified: false as const }
}
