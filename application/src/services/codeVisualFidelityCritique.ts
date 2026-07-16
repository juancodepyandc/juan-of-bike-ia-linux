import type { VisualFidelityReport } from './codeVisualFidelity.ts'
import { buildRenderedVisualAuditCritique } from './codeVisualRenderAudit.ts'

export function buildVisualFidelityCritique(report: VisualFidelityReport): string {
  if (report.passed) return ''
  if (report.source === 'render_audit') return buildRenderedVisualAuditCritique(report)

  const failed = report.checks.filter((check) => !check.passed)
  return [
    '## ECHEC DU CONTROLE QUALITE VISUEL — REGENERATION OBLIGATOIRE',
    `Score actuel: ${report.score}/100 (seuil minimum: ${report.floor}).`,
    '',
    'Ta page precedente etait trop pauvre. Voici les controles qui ont echoue:',
    ...failed.map((check) => `- ${check.label}${check.evidence ? ` — ${check.evidence}` : ''}`),
    '',
    'CORRIGE ABSOLUMENT POUR LA PROCHAINE LIVRAISON:',
    failed.find((check) => check.id === 'no_scolaire_title') ? '- SUPPRIME tout titre "Bienvenue chez X" — remplace par un slogan court et fort en deux lignes.' : '',
    failed.find((check) => check.id === 'min_sections') ? '- AJOUTE des sections (objectif: 7-10): hero / anatomie / materiaux / galerie / specs / KPIs / compare / testimonials / CTA / footer.' : '',
    failed.find((check) => check.id === 'has_gradient') ? '- AJOUTE des gradients (mesh blobs en arriere-plan, gradient text sur les hero, gradient buttons).' : '',
    failed.find((check) => check.id === 'has_depth') ? '- AJOUTE de la profondeur via filter: blur(120-160px) sur des blobs absolute + backdrop-filter sur la nav.' : '',
    failed.find((check) => check.id === 'has_animations') ? '- AJOUTE des animations: @keyframes, transitions cubic-bezier, IntersectionObserver pour scroll reveal.' : '',
    failed.find((check) => check.id === 'has_inline_svg') ? '- AJOUTE au moins un SVG inline travaille (logo de la marque, icones, illustrations).' : '',
    failed.find((check) => check.id === 'has_images') ? '- UTILISE les assets fichiers via PLACEHOLDER_IMG_HERO/DETAIL/LIFESTYLE1/LIFESTYLE2 dans <img src="...">.' : '',
    failed.find((check) => check.id === 'premium_fonts') ? '- IMPORTE Inter ou Space Grotesk via Google Fonts (preconnect + display=swap).' : '',
    failed.find((check) => check.id === 'has_css_vars') ? '- DECLARE des variables CSS dans :root pour --bg, --fg, --accent, --border.' : '',
    failed.find((check) => check.id === 'has_clamp') ? '- UTILISE clamp() pour les tailles de police responsive.' : '',
    failed.find((check) => check.id === 'has_hover') ? '- AJOUTE des etats :hover sur les liens, cartes, boutons.' : '',
    failed.find((check) => check.id === 'html_size') ? '- DEVELOPPE le contenu — la page doit faire au moins 8 ko de HTML, pas 1 ko.' : '',
    failed.find((check) => check.id === 'rich_styling') ? '- DEVELOPPE le CSS — la page doit avoir au moins 2-3 ko de CSS, pas 200 lignes.' : '',
    failed.find((check) => check.id === 'has_3d_transforms') ? '- AJOUTE des transformations 3D: rotateY au scroll OU perspective + preserve-3d sur les cards (flip 3D) OU rotation continue de la bouteille/produit.' : '',
    failed.find((check) => check.id === 'has_scroll_driven') ? '- AJOUTE une animation pilotee par scroll: section sticky avec --p, IntersectionObserver, OU ScrollTrigger. Le visuel principal doit reagir au scroll.' : '',
    failed.find((check) => check.id === 'has_layered_gradients') ? '- AJOUTE au moins 2 gradients layered (mesh blobs en fond + gradient hero text).' : '',
    failed.find((check) => check.id === 'no_flat_card_cluster')
      ? '- ECHEC CRITIQUE: tu as livre des CARTES PLATES COLOREES sans images (`<div style="background:red">Texte</div>`). C est exactement le pattern interdit.\n  CORRIGE: chaque carte DOIT contenir soit un <img src="PLACEHOLDER_IMG_*">, soit un SVG inline travaille (>100 chars), soit un canvas. Les cards sans visuel sont REJETEES.\n  Si tu utilises des cards (saveurs, materiaux, produits, services), CHACUNE doit avoir une image au-dessus du texte.'
      : '',
    '',
    'Reprends le STARTER TEMPLATE fourni et remplace UNIQUEMENT les {{slots}} par du contenu adapte. NE simplifie PAS le squelette.',
    'AUCUN DIV avec `background: <couleur unie>` SANS image/svg/canvas a l interieur. Aucune exception.',
  ].filter(Boolean).join('\n')
}
