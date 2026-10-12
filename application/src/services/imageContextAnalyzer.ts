import { ollamaChat } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'

export interface ImageContextAnalysis {
  intent: 'new_idea' | 'modification'
  masterPrompt: string
  reasoning: string
}

const SYSTEM_PROMPT = `Tu es le chef d'orchestre du module de génération d'image (FLUX).
Ton rôle est d'analyser l'historique de la conversation et la nouvelle requête de l'utilisateur pour déterminer le contexte exact de la demande, sans AUCUNE perte d'historique.

Règles impératives :
1. Analyse l'historique fourni. Identifie le sujet principal, l'environnement, le style, les vêtements, et les détails précédemment établis.
2. Détermine si la nouvelle requête est une 'new_idea' (nouvelle image, on oublie le contexte précédent) ou une 'modification' (on garde le contexte et on applique le changement : ex. ajout de personnage, changement de vêtement, retouche du décor).
3. Si c'est une 'modification', tu DOIS générer un 'masterPrompt' qui est une description visuelle complète, autonome, et détaillée de la scène finale. Ce masterPrompt DOIT inclure tous les éléments de l'historique qu'on souhaite conserver, ET les modifications demandées.
4. Réponds STRICTEMENT au format JSON, sans aucun autre texte autour, avec la structure exacte suivante :
{
  "intent": "new_idea" | "modification",
  "masterPrompt": "la description visuelle complète en anglais, optimisée pour un modèle de diffusion (FLUX)",
  "reasoning": "une courte explication de ton choix"
}`

export async function analyzeImageContext(
  history: { role: string; content: string }[],
  currentPrompt: string
): Promise<ImageContextAnalysis> {
  const model = useAppStore.getState().mainModel

  const historyContext = history.length > 0
    ? history.map(msg => `${msg.role.toUpperCase()}: ${msg.content}`).join('\n')
    : 'Aucun historique.'

  const userMessage = `Historique de la session :\n${historyContext}\n\nNouvelle requête :\nUSER: ${currentPrompt}`

  try {
    const response = await ollamaChat(
      model,
      [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: userMessage }
      ],
      0.1 // Température basse pour avoir un JSON consistant
    )

    const content = typeof response === 'string'
      ? response
      : response?.message?.content || '{}'

    // Tentative de parsing propre (on gère les éventuels backticks markdown du LLM)
    const jsonMatch = content.match(/\{[\s\S]*\}/)
    const jsonString = jsonMatch ? jsonMatch[0] : content

    return JSON.parse(jsonString) as ImageContextAnalysis
  } catch (error) {
    console.warn("Erreur lors de l'analyse sémantique LLM, fallback sur le prompt brut.", error)
    // Fallback gracieux en cas d'erreur de parsing ou de modèle
    return {
      intent: history.length > 0 ? 'modification' : 'new_idea',
      masterPrompt: currentPrompt,
      reasoning: "Erreur de fallback"
    }
  }
}
