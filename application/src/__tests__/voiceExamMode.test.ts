import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildVoiceExamOpener,
  buildVoiceExamPromptBlock,
  buildVoiceExamReport,
  defaultVoiceExamCriteria,
  formatVoiceExamClock,
  formatVoiceExamDuration,
  extractVoiceExamQuestionPool,
  heuristicVoiceExamGrade,
  isGrandOral,
  isInteractiveExam,
  isPresentationEndSignal,
  parseVoiceExamGrade,
  pickVoiceExamQuestion,
  parseVoiceExamDuration,
  validateVoiceExamConfig,
  type VoiceExamConfig,
} from '../services/voiceExamMode.ts'

function makeConfig(overrides: Partial<VoiceExamConfig> = {}): VoiceExamConfig {
  return {
    subject: 'anglais LV1',
    durationSec: 600,
    format: 'mixed',
    planText: '',
    questionsText: 'Present yourself and answer the jury questions.',
    documents: [],
    ...overrides,
  }
}

describe('voiceExamMode validation', () => {
  test('refuse une session totalement vide (ni sujet, ni fichier, ni plan, ni questions)', () => {
    const result = validateVoiceExamConfig(makeConfig({ subject: '', planText: '', questionsText: '', documents: [] }))
    assert.equal(result.ok, false)
    assert.match(result.errors.join(' '), /sujet|questions/i)
  })

  test('accepte un entretien interactif avec seulement un sujet (Aurora improvise)', () => {
    const result = validateVoiceExamConfig(makeConfig({
      format: 'questions', subject: 'le rechauffement climatique', planText: '', questionsText: '', documents: [],
    }))
    assert.equal(result.ok, true)
  })

  test('refuse un oral continu sans sujet ni plan ni questions', () => {
    const result = validateVoiceExamConfig(makeConfig({
      format: 'presentation', subject: '', planText: '', questionsText: '', documents: [],
    }))
    assert.equal(result.ok, false)
  })

  test('accepte questions seules quand aucun plan nest fourni', () => {
    const result = validateVoiceExamConfig(makeConfig({ planText: '', questionsText: 'Question 1' }))
    assert.equal(result.ok, true)
  })

  test('refuse duree invalide', () => {
    const result = validateVoiceExamConfig(makeConfig({ durationSec: 0 }))
    assert.equal(result.ok, false)
    assert.match(result.errors.join(' '), /duree/i)
  })
})

describe('voiceExamMode interactif', () => {
  test('questions et mixed sont interactifs, presentation ne l est pas', () => {
    assert.equal(isInteractiveExam('questions'), true)
    assert.equal(isInteractiveExam('mixed'), true)
    assert.equal(isInteractiveExam('presentation'), false)
  })

  test('prompt interactif impose une question a la fois et des relances', () => {
    const prompt = buildVoiceExamPromptBlock(makeConfig({ format: 'questions', interviewer: 'jury', intensity: 'exigeant' }))
    assert.match(prompt, /MODE EXAMEN ORAL ACTIF/)
    assert.match(prompt, /UNE seule question a la fois/)
    assert.match(prompt, /relance/i)
  })

  test('opener questions tire une premiere question de la banque', () => {
    const opener = buildVoiceExamOpener(
      makeConfig({ format: 'questions', questionsText: '1. Pourquoi ce sujet ?\n2. Donne un exemple.' }),
      'fr',
      () => 0,
    )
    assert.match(opener, /Premiere question/i)
    assert.match(opener, /Pourquoi ce sujet/)
  })

  test('opener mixed invite a presenter', () => {
    const opener = buildVoiceExamOpener(makeConfig({ format: 'mixed', subject: 'la photosynthese' }), 'fr')
    assert.match(opener, /presenter|presente/i)
  })
})

describe('voiceExamMode fin de presentation', () => {
  test('detecte une fin ACCOMPLIE', () => {
    for (const phrase of [
      "j'ai terminé Aurora",
      "j'ai terminé",
      "voilà, j'ai fini",
      "c'est terminé",
      "ma présentation est terminée",
      "merci de votre attention",
      "voilà c'est tout",
      "I'm done",
      "thank you for your attention",
    ]) {
      assert.equal(isPresentationEndSignal(phrase), true, `devrait détecter: "${phrase}"`)
    }
  })

  test('IGNORE les formes futures / introductives (la conclusion fait partie de l exposé)', () => {
    for (const phrase of [
      "je vais terminer avec comme conclusion",
      "je vais terminer avec ma conclusion sur le sujet",
      "pour terminer, je dirais que c'est important",
      "en conclusion, le bilan est positif",
      "pour conclure je vais résumer",
      "je termine dans une minute",
      "et maintenant je vais finir par un dernier exemple",
    ]) {
      assert.equal(isPresentationEndSignal(phrase), false, `ne devrait PAS détecter: "${phrase}"`)
    }
  })

  test('ne se déclenche pas sur du contenu normal', () => {
    assert.equal(isPresentationEndSignal("la photosynthèse transforme le CO2 en oxygène"), false)
    assert.equal(isPresentationEndSignal(''), false)
  })
})

describe('voiceExamMode grand oral', () => {
  test('detecte le Grand Oral et applique sa grille officielle', () => {
    assert.equal(isGrandOral('Grand Oral physique'), true)
    assert.equal(isGrandOral('grand-oral'), true)
    assert.equal(isGrandOral('oral anglais LV1'), false)
    const labels = defaultVoiceExamCriteria('Grand Oral SVT', 'mixed').map((c) => c.label).join(' ')
    assert.match(labels, /Qualite orale/i)
    assert.match(labels, /argumentation/i)
    assert.match(labels, /echange avec le jury/i)
  })
})

describe('voiceExamMode correction', () => {
  test('parse un JSON de correction LLM', () => {
    const criteria = defaultVoiceExamCriteria('philo', 'mixed')
    const grade = parseVoiceExamGrade(
      '```json\n{"score20": 14.5, "verdict": "Solide", "strengths": ["clair"], "weaknesses": ["court"], "mistakes": [], "advice": ["plus d exemples"], "criteria": [{"label": "Structure", "score": 3, "max": 4, "note": "ok"}]}\n```',
      criteria,
    )
    assert.ok(grade)
    assert.equal(grade!.score20, 14.5)
    assert.deepEqual(grade!.advice, ['plus d exemples'])
  })

  test('grade heuristique reste dans 0..20 et marque le fallback', () => {
    const grade = heuristicVoiceExamGrade({
      config: makeConfig(),
      startedAt: 0,
      endedAt: 60_000,
      transcript: [{ role: 'user', text: 'Introduction puis exemple precis puis conclusion.' }],
    })
    assert.ok(grade.score20 >= 0 && grade.score20 <= 20)
    assert.equal(grade.fallback, true)
  })
})

describe('voiceExamMode criteria and prompt', () => {
  test('criteres langue incluent prononciation et relances', () => {
    const labels = defaultVoiceExamCriteria('anglais LV1', 'mixed').map((criterion) => criterion.label).join(' ')
    assert.match(labels, /Prononciation/i)
    assert.match(labels, /questions|relances/i)
  })

  test('prompt injecte documents, plan et duree', () => {
    const prompt = buildVoiceExamPromptBlock(makeConfig({
      planText: 'I. Thesis II. Examples',
      documents: [{ name: 'grille.pdf', text: 'Fluency: 5 points' }],
    }))
    assert.match(prompt, /MODE EXAMEN ORAL ACTIF/)
    assert.match(prompt, /10min/)
    assert.match(prompt, /grille\.pdf/)
    assert.match(prompt, /I\. Thesis/)
  })
})

describe('voiceExamMode duration parsing', () => {
  test('parse secondes, minutes composees et heures', () => {
    assert.equal(parseVoiceExamDuration('5s'), 5)
    assert.equal(parseVoiceExamDuration('2min 05s'), 125)
    assert.equal(parseVoiceExamDuration('1h30'), 5400)
    assert.equal(parseVoiceExamDuration('10'), 600)
    assert.equal(parseVoiceExamDuration('01:05'), 65)
  })

  test('format duration humain et horloge', () => {
    assert.equal(formatVoiceExamDuration(125), '2min 5s')
    assert.equal(formatVoiceExamDuration(5400), '1h 30min')
    assert.equal(formatVoiceExamClock(125), '02:05')
    assert.equal(formatVoiceExamClock(3665), '1:01:05')
  })
})

describe('voiceExamMode question picking', () => {
  test('extrait plusieurs questions et en tire une', () => {
    const text = '1. Faut-il proteger la biodiversite ?\n2. Le progres technique libere-t-il ?\n3. Peut-on tout prouver ?'
    const pool = extractVoiceExamQuestionPool(text)
    assert.deepEqual(pool, [
      'Faut-il proteger la biodiversite ?',
      'Le progres technique libere-t-il ?',
      'Peut-on tout prouver ?',
    ])
    assert.equal(pickVoiceExamQuestion(text, () => 0.5), 'Le progres technique libere-t-il ?')
  })
})

describe('voiceExamMode report', () => {
  test('genere un rapport markdown avec note et transcription', () => {
    const report = buildVoiceExamReport({
      config: makeConfig(),
      startedAt: 1_000,
      endedAt: 181_000,
      transcript: [
        { role: 'user', text: 'Introduction. Premierement je donne un exemple precis. Pour conclure, je reponds au sujet.' },
        { role: 'assistant', text: 'Peux-tu preciser ton exemple ?' },
      ],
    })
    assert.match(report.markdown, /# Rapport examen oral Aurora/)
    assert.match(report.markdown, /Note indicative/)
    assert.match(report.markdown, /Transcription/)
    assert.match(report.spokenSummary, /note indicative/i)
  })
})
