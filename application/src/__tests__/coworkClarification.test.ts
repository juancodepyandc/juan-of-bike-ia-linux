import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildClarificationContinuationHint,
  resolveClarificationContinuation,
} from '../services/coworkClarification.ts'

describe('cowork clarification continuation', () => {
  test('merges a short answer with the original action request', () => {
    const history = [
      {
        role: 'user' as const,
        content: 'analyse mon bureau et sort moi une fiche recap de tout',
      },
      {
        role: 'aurora' as const,
        content: 'Pourriez-vous preciser si vous souhaitez analyser votre bureau physique ou votre espace informatique ?',
      },
    ]

    const resolved = resolveClarificationContinuation('espace informatique', history)

    assert.equal(resolved?.originalRequest, 'analyse mon bureau et sort moi une fiche recap de tout')
    assert.equal(resolved?.clarificationAnswer, 'espace informatique')

    const hint = buildClarificationContinuationHint('espace informatique', history)
    assert.match(hint, /Demande originale a reprendre/)
    assert.match(hint, /analyse mon bureau/)
    assert.match(hint, /Ne donne pas une definition/)
  })

  test('merges official TP follow-up with the original BAC STI2D SIN PDF request', () => {
    const history = [
      {
        role: 'user' as const,
        content: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
      },
      {
        role: 'aurora' as const,
        content: 'Pourriez-vous preciser si vous cherchez des fichiers TP officiels sur eduscol.education.fr ou une synthese theorique sans ressources externes ?',
      },
      {
        role: 'user' as const,
        content: 'je cherche des fichiers officiel de tp',
      },
      {
        role: 'aurora' as const,
        content: 'Voulez-vous rechercher specifiquement les fichiers TP officiels sur eduscol.education.fr ou consulter des ressources theoriques complementaires ?',
      },
    ]

    const resolved = resolveClarificationContinuation('oui', history)

    assert.match(resolved?.originalRequest || '', /fiche de revision en pdf/)
    assert.equal(resolved?.clarificationAnswer, 'oui')
    assert.match(buildClarificationContinuationHint('oui', history), /Demande originale a reprendre/)
  })

  test('ignores the current user turn if the overlay already included it in history', () => {
    const history = [
      {
        role: 'user' as const,
        content: 'analyse mon bureau et sort moi une fiche recap de tout',
      },
      {
        role: 'aurora' as const,
        content: 'Bureau physique ou espace informatique ?',
      },
      {
        role: 'user' as const,
        content: 'espace informatique',
      },
    ]

    const resolved = resolveClarificationContinuation('espace informatique', history)

    assert.equal(resolved?.originalRequest, 'analyse mon bureau et sort moi une fiche recap de tout')
  })

  test('does not synthesize context for a standalone short prompt', () => {
    assert.equal(resolveClarificationContinuation('espace informatique', []), null)
    assert.equal(buildClarificationContinuationHint('espace informatique', []), '')
  })

  test('does not trigger when the previous assistant turn was not a clarification question', () => {
    const history = [
      { role: 'user' as const, content: 'bonjour' },
      { role: 'aurora' as const, content: 'Salut, je peux t aider.' },
    ]

    assert.equal(resolveClarificationContinuation('espace informatique', history), null)
  })
})
