import type { CodeIntent } from './codeIntent.ts'
import { describeProductShapeHint } from './codeSystemPromptProductShapes.ts'

export function buildSubjectLockBlock(intent: CodeIntent): string {
  const subject = intent.assetPlan?.subject
  if (!subject || subject.source === 'none' || !subject.canonical) return ''

  const isBrand = subject.source === 'brand' || subject.source === 'inferred_brand'
  const profile = subject.brandProfile
  const displayName = subject.canonical
  const productKeywords = profile?.productKeywords ?? []
  const palette: string[] = []
  if (profile?.primaryColor) palette.push(`primary ${profile.primaryColor}`)
  if (profile?.secondaryColor) palette.push(`secondary ${profile.secondaryColor}`)
  if (profile?.tertiaryColor) palette.push(`tertiary ${profile.tertiaryColor}`)

  const lines: string[] = [
    '## VERROUILLAGE SUJET — REGLE INVIOLABLE (REGLE -1, AVANT TOUT)',
    '',
    `Le sujet de cette page est: **${displayName}**.`,
    `${isBrand ? 'C est une marque reelle.' : 'C est le sujet exact que l utilisateur a demande.'} Tu ne peux PAS deriver vers un sujet adjacent.`,
    '',
    '### REGLES INVIOLABLES',
    `- Le mot "${displayName}" DOIT apparaitre dans <title>, dans le <h1> du hero, et dans au moins 3 sections distinctes (en titre OU dans le corps).`,
    `- Le contenu de chaque section parle de ${displayName}, pas d un sujet generique.`,
    '- Si tu ecris un site "restaurant", "cafe generique", "blog editorial", "landing SaaS abstraite" ou tout autre sujet adjacent, c est un ECHEC TOTAL et la sortie sera rejetee automatiquement.',
    '',
  ]

  if (palette.length > 0) {
    lines.push('### PALETTE OBLIGATOIRE')
    lines.push(`- Couleurs canoniques de la marque: ${palette.join(', ')}.`)
    lines.push(`- La couleur primaire (${profile?.primaryColor}) DOIT etre utilisee pour: hero background ou accent, CTAs principaux, liens, hover states.`)
    if (profile?.secondaryColor) {
      lines.push(`- La secondaire (${profile.secondaryColor}) sert au texte sur primaire, aux backgrounds alternes ou aux details.`)
    }
    lines.push('- Tu peux utiliser des nuances (rgba, mix, gradients) mais la palette doit etre RECONNAISSABLE comme celle de la marque.')
    lines.push('')
  }

  if (productKeywords.length > 0) {
    lines.push('### PRODUITS / TERMES CLES A INTEGRER DANS LE COPY')
    lines.push(`- ${productKeywords.join(', ')}.`)
    lines.push('- Au moins 2 de ces termes doivent apparaitre dans les titres de section ou dans le hero.')
    lines.push('')
  }

  if (profile?.designVibe) {
    lines.push('### VIBE VISUEL ATTENDUE')
    lines.push(`- ${profile.designVibe}.`)
    if (profile.typoVibe) lines.push(`- Typo: ${profile.typoVibe}.`)
    lines.push('')
  }

  lines.push('### ASSETS REELS DEJA TELECHARGES POUR TOI')
  lines.push('- L orchestrateur a pre-telecharge des images reelles de la marque/sujet, encodees en data URL.')
  lines.push('- Tu DOIS les utiliser dans la page en placant les markers literaux suivants comme valeur de `src=` (ils seront remplaces a la fin):')
  lines.push('  - `PLACEHOLDER_SUBJECT_IMG`     → image principale (hero produit OU logo).')
  lines.push('  - `PLACEHOLDER_SUBJECT_IMG_1`   → image secondaire (lifestyle / contexte).')
  lines.push('  - `PLACEHOLDER_SUBJECT_IMG_2`   → image alternative (gallery / showcase).')
  lines.push('  - `PLACEHOLDER_SUBJECT_IMG_3`   → image complementaire (detail / texture).')
  lines.push('- Place ces markers a des endroits strategiques: <img src="PLACEHOLDER_SUBJECT_IMG_1" alt="..." loading="lazy" />.')
  lines.push('- Si un marker n a pas d image associee a la fin, il restera litteral mais ne casse pas la page (le `<img>` ne charge simplement rien). Les premiers markers sont les plus surs.')
  lines.push('- Au minimum: utilise PLACEHOLDER_SUBJECT_IMG dans le hero ET PLACEHOLDER_SUBJECT_IMG_1 dans une section showcase/gallery.')
  lines.push('')

  if (isBrand) {
    lines.push('### EFFETS 3D / GRAPHISME PUSHED (quand le prompt user le demande)')
    lines.push('- Si le prompt mentionne "graphisme", "3D", "ultra stylise", "effet": tu DOIS pousser au-dela d une landing plate.')
    lines.push('- Options acceptables (au moins UNE):')
    lines.push('  - Bouteille/canette/produit en CSS 3D (rotation, perspective, transform-style: preserve-3d).')
    lines.push('  - Particle system canvas (bulles pour soda, etoiles pour tech, flammes pour food, etc.) en plein hero.')
    lines.push('  - Three.js minimal via CDN ESM (jsdelivr 0.160) avec un objet brand-relevant en rotation OrbitControls.')
    lines.push('  - Parallax scroll multi-layer avec les images PLACEHOLDER_SUBJECT_IMG_* qui se decoupent en couches.')
    lines.push('  - Mesh gradient anime aux couleurs de la marque + noise texture + glow pulse sur le produit.')
    lines.push('')

    if (profile?.productShape) {
      const shapeHint = describeProductShapeHint(profile.productShape, displayName, profile.primaryColor)
      if (shapeHint) {
        lines.push('### FORME 3D PROCEDURALE RECOMMANDEE')
        lines.push(shapeHint)
        lines.push('')
        lines.push('### HALO SHADER FRESNEL (associe a la recipe ci-dessus — OBLIGATOIRE)')
        lines.push(`Apres avoir cree le mesh principal du produit (${profile.productShape}), tu DOIS ajouter immediatement le halo shader Fresnel:`)
        lines.push('  1. Cree un new THREE.ShaderMaterial avec le code copy-paste fourni dans la section "EFFET SHADER GLSL SIGNATURE" de la reference design (vertexShader vNormalW + vViewDir, fragmentShader fresnel pow 3 + pulse sin, AdditiveBlending).')
        lines.push(`  2. Substitue PRIMARY_COLOR_HEX par "${profile.primaryColor}" dans uColor.`)
        lines.push('  3. Cree un mesh halo = new THREE.Mesh(productMesh.geometry, haloMat), halo.scale.setScalar(1.08).')
        lines.push('  4. productMesh.add(halo).')
        lines.push('  5. Dans le requestAnimationFrame loop: haloMat.uniforms.uTime.value = clock.getElapsedTime().')
        lines.push('Si tu omets ce halo, la sortie est REJETEE par la gate de fidelite (shader_present:false declenche un retry force).')
        lines.push('')
      }
    }
  }

  lines.push('### INTERDICTIONS ABSOLUES SUR LE SUJET')
  lines.push(`- Inventer un sous-sujet ("la qualite culinaire", "l excellence du service", "blog sur les boissons") deconnecte de ${displayName}.`)
  lines.push(`- Mentionner ${displayName} UNE seule fois et remplir le reste avec du copy generique.`)
  lines.push('- Ignorer la palette canonique pour utiliser le violet/cyan/ambre du starter premium.')
  lines.push('- Ne placer aucun PLACEHOLDER_SUBJECT_IMG dans la page (alors que des images reelles ont ete preparees).')
  lines.push('')
  lines.push(`Cette regle prime sur le DESIGN CONTRACT et sur la REFERENCE PREMIUM. Si un conflit apparait, ${displayName} gagne toujours.`)
  return lines.join('\n')
}
