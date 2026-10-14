type Message = { role: string; content: string }
const FUNCTION_WORDS = new Set('un une le la les de du des en et a avec sans pour dans au aux une fais faire genere generer generation cree creer creerait modele model objet object 3d representation figurine personnage entièrement entier entire full create generate make please stp the a an of with without for'.normalize('NFD').replace(/[\u0300-\u036f]/g,'').split(' '))
function anchor(text: string): string | undefined {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().split(/[^\p{L}\p{N}]+/u).find(word => word.length > 2 && !FUNCTION_WORDS.has(word) && !/^\d+$/.test(word))
}
export function retainThreeDRequirements(prompt: string, history: Message[], explicitEdit = false): Message[] {
  const users = history.filter(message => message.role === 'user')
  const previous = users[users.length - 1]
  if (!previous) return []
  const sameSubject = Boolean(anchor(prompt) && anchor(prompt) === anchor(previous.content))
  const normalized = prompt.normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase()
  const exclusionEdit = /^(?:sans\s+(?!changer\b|modifier\b|toucher\b)|without\s+(?!changing\b|modifying\b)|pas de\s|no\s)/.test(normalized)
  return sameSubject || explicitEdit || exclusionEdit ? users.slice(-4) : []
}
export function composeThreeDRequirements(prompt: string, history: Message[]): string {
  if (!history.length) return prompt
  return `Previous user requirements for the same subject (retain unless explicitly changed):\n${history.map(message => message.content).join('\n\n')}\n\nCurrent user request (latest explicit changes take priority):\n${prompt}`
}
