/**
 * v82hc : bouton ★ favori réutilisable entre les V1 views (Image,
 * Code, Drawing, Video, 3D). Sauve le prompt courant dans le
 * promptLibraryStore avec le module + parameters/tags fournis.
 *
 * - Conditionnel sur prompt.trim() && !disabled (parent décide si
 *   generating/streaming).
 * - Feedback ✓ ajouté pendant 1500ms après save.
 * - Style OKLCH gold → vert quand feedback, transitions 150ms.
 *
 * Props :
 *   prompt : texte du prompt à sauver (le parent passe le state).
 *   module : ModuleId pour le tag.
 *   parameters? : extra params à persister (style, aspect, etc.)
 *   tags? : tags additionnels (le module et le style sont auto).
 *   disabled? : skip si generating en cours.
 *   compact? : version icon-only sans label.
 */
import { useState } from 'react'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import type { ModuleId } from '../types/app'

interface Props {
  prompt: string
  module: ModuleId
  parameters?: Record<string, unknown>
  tags?: string[]
  disabled?: boolean
  fidelityScore?: number
  title?: string
}

export default function FavoriteButton({
  prompt, module, parameters, tags, disabled, fidelityScore = 95,
  title = 'Sauver ce prompt dans la bibliothèque (favoris persistants)',
}: Props) {
  const { addPrompt, prompts } = usePromptLibraryStore()
  const [feedback, setFeedback] = useState(false)
  const trimmed = prompt.trim()
  // v82hg : count des favoris déjà sauvés pour ce module (toujours rendu
  //   comme badge même si aucun draft n'est tapé — UX informative).
  const moduleCount = prompts.filter((p) => p.module === module).length
  // v82hg : détection si le prompt courant existe déjà dans la library
  //   (évite doublons, l'user voit un état différent du bouton).
  const alreadySaved = !!trimmed && prompts.some((p) =>
    p.module === module && p.prompt === trimmed,
  )

  // Conteneur flex qui rend le badge même quand le bouton est null.
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {trimmed && !disabled && (
        <button type="button"
          onClick={() => {
            if (alreadySaved) return
            addPrompt({
              module,
              prompt: trimmed,
              fidelityScore,
              parameters: parameters ?? {},
              tags: tags ?? [module],
            })
            setFeedback(true)
            window.setTimeout(() => setFeedback(false), 1500)
          }}
          disabled={alreadySaved}
          title={alreadySaved
            ? 'Ce prompt est déjà dans tes favoris'
            : title}
          style={{
            marginLeft: 6, padding: '6px 12px',
            background: feedback
              ? 'oklch(0.70 0.13 145 / 0.20)'
              : alreadySaved
              ? 'oklch(0.78 0.10 145 / 0.08)'
              : 'oklch(0.78 0.16 80 / 0.10)',
            color: feedback
              ? 'oklch(0.78 0.16 145)'
              : alreadySaved
              ? 'oklch(0.70 0.10 145)'
              : 'oklch(0.78 0.16 80)',
            border: `1px solid ${feedback
              ? 'oklch(0.78 0.16 145 / 0.5)'
              : alreadySaved
              ? 'oklch(0.78 0.10 145 / 0.3)'
              : 'oklch(0.78 0.16 80 / 0.45)'}`,
            fontSize: 11, fontWeight: 700,
            fontFamily: 'var(--font-mono, monospace)',
            cursor: alreadySaved ? 'default' : 'pointer',
            opacity: alreadySaved ? 0.7 : 1,
            borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 4,
            transition: 'background .15s ease, color .15s ease, border .15s ease',
          }}>
          {feedback ? '✓ ajouté' : alreadySaved ? '★ déjà' : '★ favori'}
        </button>
      )}
      {/* v82hg : badge count si au moins 1 favori dans ce module */}
      {moduleCount > 0 && (
        <span
          title={`${moduleCount} favori${moduleCount > 1 ? 's' : ''} sauvé${moduleCount > 1 ? 's' : ''} pour ce module · Settings (Cmd+,) → Mes prompts favoris`}
          onClick={() => {
            window.dispatchEvent(new KeyboardEvent('keydown', {
              key: ',', metaKey: true, ctrlKey: true, bubbles: true,
            }))
          }}
          style={{
            padding: '2px 6px', fontSize: 9,
            fontFamily: 'var(--font-mono, monospace)',
            color: 'oklch(0.78 0.16 80)',
            background: 'oklch(0.78 0.16 80 / 0.05)',
            border: '1px solid oklch(0.78 0.16 80 / 0.20)',
            borderRadius: 3, cursor: 'pointer',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '0.05em',
          }}>
          {moduleCount}★
        </span>
      )}
    </span>
  )
}
