/**
 * Run 1161 — la porte savait qu une section etait vide, pas OU elle vivait.
 *
 * Preuve rendue au correcteur: « Torréfié cette semaine, : 944px remplie a 9% »,
 * sur un projet de 31 fichiers. La passe ciblee a reecrit AdminPage, ContactPage,
 * HomePage, MarketCalendarPage, SubscriptionPage et index.css — et jamais
 * `src/components/HeroSection.tsx`, seul fichier a contenir cette section.
 *
 * Les extraits ci-dessous sont ceux du livrable reel
 * (output/code_assets/viewers/run-1161/project.json).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { attributeSectionToFile, attributeSections, selectorTokens } from '../services/codeCompositionAttribution.ts'

const HERO = `import React from 'react'
import { motion } from 'framer-motion'

const HeroSection: React.FC = () => {
  return (
    <motion.section className="hero-section">
      <div className="hero-content">
        <motion.h1 className="hero-title">
          Torréfié cette semaine,
          <br />
          pas l'an dernier
        </motion.h1>
        <motion.p className="hero-subtitle">Artisanal, direct-trade et chaleureux</motion.p>
      </div>
    </motion.section>
  )
}

export default HeroSection;`

const HOME = `import HeroSection from '../components/HeroSection'
import CoffeeCard from '../components/CoffeeCard'

export default function HomePage() {
  return <main><HeroSection /><section className="coffees"><h2>Cafés du moment</h2></section></main>
}`

const FILES = [
  { name: 'src/components/HeroSection.tsx', content: HERO },
  { name: 'src/pages/HomePage.tsx', content: HOME },
  { name: 'src/styles/index.css', content: '.hero-section { min-height: 100vh; }' },
]

describe('attribution d une section rendue a son fichier source', () => {
  test('le cas reel du run 1161: le hero remonte a HeroSection.tsx', () => {
    const found = attributeSectionToFile(
      { selector: 'section.hero-section', label: 'Torréfié cette semaine, ' },
      FILES,
    )
    assert.equal(found, 'src/components/HeroSection.tsx')
  })

  test('la classe seule suffit quand le texte est absent', () => {
    assert.equal(attributeSectionToFile({ selector: 'section.hero-section' }, FILES), 'src/components/HeroSection.tsx')
  })

  test('le texte seul suffit quand la section n a pas de classe', () => {
    assert.equal(
      attributeSectionToFile({ selector: 'section', label: 'Cafés du moment' }, FILES),
      'src/pages/HomePage.tsx',
    )
  })

  test('une feuille de style n est jamais designee comme porteuse de section', () => {
    const found = attributeSectionToFile({ selector: 'section.hero-section', label: '' }, [
      { name: 'src/styles/index.css', content: '.hero-section { min-height: 100vh; }' },
    ])
    assert.equal(found, null)
  })

  test('rien ne designe rien: on ne devine pas', () => {
    assert.equal(attributeSectionToFile({ selector: 'section.inconnue', label: 'zz' }, FILES), null)
  })

  test('un texte trop court ne fait pas preuve', () => {
    assert.equal(attributeSectionToFile({ selector: 'section', label: 'Cafés' }, FILES), null)
  })

  test('les tokens ignorent le nom de balise et le bruit court', () => {
    assert.deepEqual(selectorTokens('section#top.hero-section.a'), ['top', 'hero-section'])
    assert.deepEqual(selectorTokens(undefined), [])
  })

  test('attributeSections ne perd aucune section et n en invente aucune source', () => {
    const out = attributeSections(
      [{ selector: 'section.hero-section', label: 'Torréfié cette semaine, ' }, { selector: 'footer', label: 'zz' }],
      FILES,
    )
    assert.equal(out.length, 2)
    assert.equal(out[0].sourceFile, 'src/components/HeroSection.tsx')
    assert.equal(out[1].sourceFile, undefined)
  })
})
