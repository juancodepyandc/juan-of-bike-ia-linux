// Diagnostic SANS GPU : prouve la divergence UI vs CLI sur l'instruction Kontext
// pour un meme prompt "ajoute le personnage Jax". Montre que l'UI injecte le
// sessionContract (tokens "shoulders/chest volume/body" -> guidage positif,
// d'ou le sujet rendu plus muscle), alors que le CLI envoie une instruction propre.
import { parseImageIntent } from '../../application/src/utils/imagePromptParser.ts'
import { buildKontextInstruction } from '../../application/src/utils/fluxKontextWorkflow.ts'
import { buildImageAutocorrectionContract } from '../../application/src/services/imageConversationContract.ts'
import { buildPromptContractBlock, parseBrief } from '../../application/src/services/imagePromptBuilder.ts'
import {
  detectNamedAddTarget, describeNamedEntity, buildEntityAppearanceClause,
} from '../../application/src/utils/namedEntityEnrichment.ts'

const prompt = process.argv[2]
  || 'ajoute le personnage Jax de The Amazing Digital Circus posant amicalement une main sur mon épaule'

const intent = parseImageIntent(prompt, { hasReference: true })
const namedTarget = detectNamedAddTarget(prompt)
const desc = namedTarget ? await describeNamedEntity(namedTarget, {}, prompt) : ''
const entityClause = desc ? buildEntityAppearanceClause(namedTarget, desc) : ''

// englishCore simule : ici on garde le FR brut pour isoler l'effet du contrat
const englishCore = 'Add the character Jax, placing a hand on my shoulder in a friendly way'

const sessionContract = buildImageAutocorrectionContract({ prompt, hasReference: true })
const promptContract = buildPromptContractBlock(parseBrief(prompt))

console.log('=== INTENT ===')
console.log('mode:', intent.editMode, '| additions:', JSON.stringify(intent.additions))
console.log('namedTarget:', namedTarget, '| entityClause:', entityClause ? 'oui' : 'non')

// ---- Instruction CLI (actuelle) : propre ----
const cliInstruction = buildKontextInstruction(
  [englishCore, entityClause].filter(Boolean).join('\n\n'),
  intent,
  { englishCore: [englishCore, entityClause].filter(Boolean).join('\n\n') },
)

// ---- Instruction UI (actuelle) : polluee par sessionContract ----
const uiInstruction = buildKontextInstruction(
  [prompt, entityClause, sessionContract].filter(Boolean).join('\n\n'),
  intent,
  { englishCore: [englishCore, entityClause, sessionContract].filter(Boolean).join('\n\n') },
)

console.log('\n=== INSTRUCTION CLI (longueur ' + cliInstruction.length + ') ===')
console.log(cliInstruction)
console.log('\n=== INSTRUCTION UI (longueur ' + uiInstruction.length + ') ===')
console.log(uiInstruction)

const risky = ['shoulder', 'chest volume', 'body volume', 'enlarge', 'proportions', 'anatomy', 'muscular', 'torso']
const hits = risky.filter((w) => new RegExp(w, 'i').test(uiInstruction))
console.log('\n=== TOKENS A RISQUE presents dans instruction UI (deviennent guidage POSITIF) ===')
console.log(hits.length ? hits.join(', ') : 'aucun')
const hitsCli = risky.filter((w) => new RegExp(w, 'i').test(cliInstruction))
console.log('Tokens a risque dans instruction CLI:', hitsCli.length ? hitsCli.join(', ') : 'aucun')
