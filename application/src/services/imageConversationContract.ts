import type { ConversationSession, ModuleHistoryMessage } from '../stores/moduleHistoryStore'
import type { FluxStyle } from '../utils/fluxWorkflow'

type StyleResolutionInput = {
  style: FluxStyle
  prompt: string
  hasReference: boolean
  isEditIntent: boolean
}

type ContractInput = {
  prompt: string
  hasReference: boolean
  conversationContext?: string
}

const HUMAN_PHOTO_EDIT_RE = /\b(photo|selfie|personne|visage|peau|corps|epaule|epaules|portrait|humain|humaine|human|skin|face|shoulder|body|amical|amitie|ami|amie|copine|copain|personnage|character|friend|companion)\b/i
const EXPLICIT_TECHNICAL_RE = /\b(rendu technique|technical render|schema|schematic|blueprint|cad|product render|studio product|produit seul|objet technique|mechanical|mecanique|connecteur|connector|cable|component|composant)\b/i
const ADDED_CHARACTER_RE = /\b(personnage|perso|personne|mascotte|character|mascot|figure|hero|heroine|villain|ami|amie|copain|copine|compagnon|compagne|friend|companion|chat|cat|animal|creature|creature|exceed)\b/i
const ADD_ENTITY_CONTEXT_RE = /\b(ajout|ajoute|ajouter|rajout|rajoute|rajouter|insertion|insere|inserer|mets|met|mettre|place|placer|pose|poser|incruste|incruster|integre|integrer|avec|add|insert|put|place|with)\b/i
const SOCIAL_INTERACTION_RE = /\b(amical|amitie|ami|amie|copain|copine|friend|companion|hug|calin|enlace|enlacer|bras autour|main sur|epaule|shoulder|hand on shoulder|arm around|pose ensemble|ensemble|a cote|cote a cote|beside|together)\b/i
const DECOR_CHANGE_RE = /\b(decor|fond|arriere.?plan|background|environnement|scene|lieu|endroit|plage|foret|ville|rue|chambre|studio|cirque|circus|stage|tent|univers|monde)\b/i
const OUTFIT_EDIT_RE = /\b(tenue|vetement|habit|habits|robe|shirt|tee.?shirt|t.?shirt|short|pantalon|maillot|couleur|rouge|noir|bleu|vert|outfit|clothes|clothing|dress|swimsuit)\b/i
const POSE_EDIT_RE = /\b(pose|assis|assise|debout|allonge|allongee|couche|couchee|genoux|bras|main|jambe|regard|expression|sourire|framing|cadrage|composition|sitting|standing|lying)\b/i
const REMOVAL_OR_REPLACE_RE = /\b(suppression|retrait|effacement|enleve|enlever|retire|retirer|supprime|supprimer|efface|effacer|remplace|remplacer|removal|deletion|replace|remove|delete|erase|sans\s+(?!changer\b|modifier\b|toucher\b|alterer\b|alterer\b|deformer\b|abimer\b|perdre\b|effacer\b)|without\s+(?!changing\b|modifying\b|touching\b|altering\b|deforming\b|damaging\b|losing\b|erasing\b))\b/i
const PERSON_TARGET = '(?:personne|personnage|humain|humaine|homme|femme|garcon|fille|gars|mec|meuf|sujet|ami|amie|copain|copine|person|character|human|man|woman|boy|girl|guy|dude|subject|friend)'
const PERSON_REMOVAL_TARGET_RE = new RegExp(`\\b(?:suppression|retrait|effacement|removal|deletion)\\b\\s*(?:complete|totale|entiere|full|total|entire)?\\s*(?:de\\s+l[' ]?|de\\s+la\\s+|du\\s+|des\\s+|de\\s+|the\\s+|a\\s+|an\\s+)?${PERSON_TARGET}\\b|\\b(?:enleve|enlever|retire|retirer|supprime|supprimer|efface|effacer|remove|delete|erase|sans|without)\\b\\s+(?:de\\s+l[' ]?|de\\s+la\\s+|du\\s+|des\\s+|le\\s+|la\\s+|l[' ]?|un\\s+|une\\s+|the\\s+|a\\s+|an\\s+)?${PERSON_TARGET}\\b`, 'i')

function normalizeText(text: string) {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function compact(text: string, max = 260) {
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max - 1)}...` : clean
}

export function resolveImageConversationStyle(input: StyleResolutionInput): {
  style: FluxStyle
  overrideReason: string | null
} {
  const normalized = normalizeText(input.prompt).toLowerCase()

  if (
    input.style === 'technical_render'
    && input.hasReference
    && input.isEditIntent
    && HUMAN_PHOTO_EDIT_RE.test(normalized)
    && !EXPLICIT_TECHNICAL_RE.test(normalized)
  ) {
    return {
      style: 'none',
      overrideReason: 'Style Technique neutralise pour preserver une retouche photo humaine naturelle.',
    }
  }

  return { style: input.style, overrideReason: null }
}

export function buildImageConversationContext(
  messages: Pick<ModuleHistoryMessage, 'role' | 'content'>[],
  maxMessages = 8,
) {
  return messages
    .slice(-maxMessages)
    .map((message) => {
      const content = message.content
        .replace(/\[image:[^\]]+\]/gi, '[previous image output]')
        .replace(/\[id:[^\]]+\]/gi, '')
        .replace(/^style:/i, 'style:')
      return `${message.role.toUpperCase()}: ${compact(content, 240)}`
    })
    .join('\n')
}

export function findLastUserPrompt(session: ConversationSession | null | undefined) {
  if (!session) return ''
  return [...session.messages].reverse().find((message) => message.role === 'user')?.content ?? ''
}

export function classifyImageEditRequest(prompt: string, hasReference = false) {
  const normalized = normalizeText(prompt).toLowerCase()
  const hasAddEntityContext = ADD_ENTITY_CONTEXT_RE.test(normalized)
  const withoutLeadingWord = prompt.replace(/^\s*[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'_-]+\b/u, '')
  const hasNamedAddedEntity = hasAddEntityContext && /\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9'_-]{2,}\b/u.test(withoutLeadingWord)
  return {
    humanPhotoEdit: hasReference || HUMAN_PHOTO_EDIT_RE.test(normalized),
    addedCharacter: hasAddEntityContext && (ADDED_CHARACTER_RE.test(normalized) || hasNamedAddedEntity),
    socialInteraction: SOCIAL_INTERACTION_RE.test(normalized),
    decorChange: DECOR_CHANGE_RE.test(normalized),
    outfitEdit: OUTFIT_EDIT_RE.test(normalized),
    poseEdit: POSE_EDIT_RE.test(normalized),
    removalOrReplace: REMOVAL_OR_REPLACE_RE.test(normalized),
    personRemovalOrReplace: PERSON_REMOVAL_TARGET_RE.test(normalized),
  }
}

export function buildImageAutocorrectionContract(input: ContractInput) {
  const traits = classifyImageEditRequest(input.prompt, input.hasReference)

  const lines = [
    'IMAGE MODULE SESSION CONTRACT - HARD REQUIREMENTS:',
    '- Treat this request as a continuation of the active Image conversation, not as an isolated one-shot prompt.',
    '- Previous user corrections are constraints: do not repeat the same failure mode in the next image.',
    '- If the user says "la photo", "ancien resultat", "celle-ci", "comme ca" or similar, use the active session and current/reference image as the visual source.',
    '- Before final output, self-check the result against the user request and reject obvious drift: wrong pose, wrong decor, missing requested character, random sticker insertion, broken anatomy, or degraded skin texture.',
  ]

  if (input.conversationContext?.trim()) {
    lines.push('RECENT IMAGE CONVERSATION CONTEXT:')
    lines.push(input.conversationContext.trim())
  }

  if (traits.humanPhotoEdit) {
    lines.push(
      'HUMAN PHOTO PRESERVATION:',
      '- Preserve the original person identity, face structure, natural body proportions, shoulders, neck, chest volume, hairline and skin tone unless the user explicitly asks to change them.',
      '- Do not enlarge shoulders, erase body volume, shrink anatomy, distort the neck, or flatten the torso.',
      '- Skin must remain natural camera skin: no granite effect, no wax filter, no painted pores, no plastic smoothing, no artificial texture overlay.',
      '- Clothing/background/character edits must not restyle untouched face or body regions.',
    )
  }

  if (traits.addedCharacter) {
    lines.push(
      'ADDED CHARACTER / ENTITY INTEGRATION:',
      '- The requested character, person, mascot or named entity must be visually identifiable as that requested entity, not replaced by a generic person or unrelated substitute.',
      '- Integrate the added entity in the same continuous image with matching camera direction, scale, perspective, lighting, shadows and occlusion.',
      '- Do not paste the new entity as a flat sticker, background prop or disconnected cut-out.',
    )
  }

  if (traits.socialInteraction) {
    lines.push(
      'SOCIAL / EMOTIONAL INTERACTION:',
      '- Show a readable friendly relationship: close placement, coherent shared pose, natural contact such as a hand on the shoulder or an arm around the neck/shoulder when requested.',
      '- The emotion or relationship requested by the user must be legible in posture, distance, gaze/contact and body language.',
      '- The companion may lean, sit, stand, appear beside, behind, above or partly horizontal if that best matches the source photo and requested composition.',
    )
  }

  if (traits.decorChange) {
    lines.push(
      'DECOR / BACKGROUND CHANGE:',
      '- If the user requests a new decor, background, world, place or named environment, the environment must visibly become that requested setting.',
      '- Keep foreground subjects anchored with plausible ground contact, matching color temperature, shadows and perspective.',
      '- Do not leave the old background dominant unless the user asked for a subtle edit.',
    )
  }

  if (traits.outfitEdit) {
    lines.push(
      'OUTFIT / COLOR EDIT:',
      '- Apply clothing, accessory and color changes exactly where requested while preserving the real body proportions underneath.',
      '- Do not erase natural body volume, change identity, or invent unrelated clothing details.',
      '- Colors requested by the user are hard constraints, not optional style hints.',
    )
  }

  if (traits.poseEdit) {
    lines.push(
      'POSE / COMPOSITION EDIT:',
      '- Apply the requested pose, framing, orientation or composition with coherent anatomy and physically possible limb placement.',
      '- Preserve recognizable identity and avoid shoulder, neck, hand, arm or leg distortions.',
    )
  }

  if (traits.removalOrReplace) {
    lines.push(
      'REMOVAL / REPLACEMENT EDIT:',
      '- Fully remove or replace the requested target; no ghost outlines, leftovers, duplicate old/new versions or blurry inpaint patch.',
      '- Reconstruct the revealed area with plausible background texture, lighting and perspective.',
    )
    if (traits.personRemovalOrReplace) {
      lines.push(
        '- When removing a person or character, remove every visible part of that target: face, head, body, clothing, shirt fabric, straps, accessories, shadows, contact edges and occlusion remnants.',
        '- Do not let added characters sit on clothing, body volume or shoulder remnants from the removed person; anchor them on the requested remaining subject or reconstructed scene.',
        '- Do not replace the removed person with enlarged anatomy from the remaining subject: no oversized shoulder, expanded chest, widened torso, stretched neck, new skin mass or invented body support.',
      )
      if (traits.addedCharacter) {
        lines.push(
          'MULTI-STAGE PERSON REMOVAL + CHARACTER PLACEMENT:',
          '- Treat this as staged editing: pass 1 removes the person and all garments; pass 2 reconstructs the revealed background and real remaining anatomy; pass 3 places the new character with correct scale/contact.',
          '- Reject the result if any removed clothing/body remains, if the support anatomy is oversized or invented, or if the new character is tiny, floating, generic, or sitting on removed-person remnants.',
        )
      }
    }
  }

  return lines.join('\n')
}
