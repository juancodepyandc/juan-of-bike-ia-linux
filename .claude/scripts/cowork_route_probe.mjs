// Pure-function probe of how Cowork routes "création / écoute / accompagnement"
// requests. No LLM, no network — just the deterministic classifiers that decide
// whether the planner will ACT or stay passive (just reply/ask).
import { resolveCoworkConversationFrame } from '../../application/src/services/coworkConversation.ts'
import { classifyCoworkMission } from '../../application/src/services/coworkMission.ts'

const PROMPTS = [
  // creation
  ['crée un fichier idees.md avec 5 idées de startup détaillées', 'création fichier'],
  ['génère une image de logo minimaliste pour un café', 'création média'],
  // listening / accompaniment / coaching
  ['écoute, je suis débordé en ce moment, aide-moi à m\'organiser pour la semaine', 'écoute/accompagnement'],
  ['j\'ai un entretien d\'embauche vendredi, accompagne-moi pour le préparer', 'accompagnement'],
  ['aide-moi à réfléchir à ma reconversion professionnelle', 'réflexion accompagnée'],
  ['je me sens perdu dans mon projet, peux-tu m\'aider à y voir clair', 'soutien'],
  ['planifie ma semaine de révision du bac', 'planification'],
  ['conseille-moi pour gérer mon budget ce mois-ci', 'conseil actionnable'],
  ['motive-moi et propose un plan pour reprendre le sport', 'coaching'],
  // control
  ['merci', 'politesse (doit rester discussion)'],
]

console.log('PROMPT | mode | shouldExecute | mission | confiance')
console.log('-------|------|---------------|---------|----------')
for (const [p, tag] of PROMPTS) {
  const frame = resolveCoworkConversationFrame(p, [])
  const mission = classifyCoworkMission(p)
  console.log(
    `[${tag}] "${p.slice(0, 46)}${p.length > 46 ? '…' : ''}"\n   → mode=${frame.mode} | shouldExecute=${frame.shouldExecute} | mission=${mission.kind} (${(mission.confidence * 100).toFixed(0)}%) | finishRule="${mission.finishRule.slice(0, 70)}…"`,
  )
}
