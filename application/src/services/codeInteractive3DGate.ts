import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'

export function checkInteractive3DFidelity(
  files: CodeFile[],
  prompt: string,
  intent?: CodeIntent,
): { ok: boolean; missing: string[]; hint: string } {
  const code = files
    .filter((file) => /\.(html?|css|m?[jt]sx?|vue|svelte)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')
  if (!code.trim()) return { ok: true, missing: [], hint: '' }

  const codeLower = code.toLowerCase()
  const promptLower = prompt.toLowerCase()
  const missing: string[] = []
  const wants3D = intent?.features.includes('3d')
    || intent?.assetPlan?.wants3D
    || /\b(3d|three\.?js|r3f|webgl|space|spaceship|vaisseau|station spatiale|asteroid|planet|orbital|cockpit|simulateur|simulator)\b/i.test(promptLower)
  const has3D = /@react-three\/fiber|@react-three\/drei|<Canvas\b|new\s+THREE\.|WebGLRenderer|three\/examples/i.test(code)
  if (!wants3D && !has3D) return { ok: true, missing: [], hint: '' }

  const wantsKeyboard = /\b(wasd|clavier|keyboard|key(?:down|up)|touches?|fleches?|arrows?|shift|boost|espace|space|pilotage|piloter|fly|voler|thrust|propulsion)\b/i.test(promptLower)
  const hasKeyboard = /\baddEventListener\s*\(\s*['"]key(?:down|up|press)['"]|onKeyDown|onKeyUp|KeyboardControls|useKeyboardControls|\.onkey(?:down|up|press)\b/i.test(code)
  const hasFrameMovement = /\b(useFrame|requestAnimationFrame|setInterval)\b/i.test(code)
    && /\b(position\.(?:x|y|z|set)|camera\.position|velocity|speed|thrust|boost|acceleration|delta)\b/i.test(code)
  if (wantsKeyboard && (!hasKeyboard || !hasFrameMovement)) {
    missing.push('pilotage clavier/WASD relie a un mouvement 3D par frame')
  }

  const wantsMinimap = /\b(minimap|mini-map|radar|scanner map|carte tactique)\b/i.test(promptLower)
  const radarLooksRandom = /\bradar[\s\S]{0,900}\bMath\.random\s*\(/i.test(code)
    || /\bblip[\s\S]{0,400}\bMath\.random\s*\(/i.test(code)
  const hasMinimap = /\b(minimap|mini-map|radar|blip|scanline|tactical-map|tacticalMap)\b/i.test(code)
    && /<svg\b|<canvas\b|\.map\s*\(|position/i.test(code)
  if (wantsMinimap && (!hasMinimap || radarLooksRandom)) {
    missing.push('minimap/radar avec positions ou blips reels, pas des points aleatoires')
  }

  const wantsWorldInteractions = /\b(collect|collecter|resource|ressource|resources|minerai|mineral|minerals|dock|docking|scanner?|scan|mission|objectif|objective)\b/i.test(promptLower)
  const hasSpatialCheck = /\b(distanceTo|raycaster|intersect|intersectsSphere|collision|collid|Math\.hypot|Vector3|Box3|Sphere)\b/i.test(code)
  const hasDomainAction = /\b(collect|resource|ressource|minerai|mineral|dock|docking|scan|scanner|mission|objective|cargo|inventory)\b/i.test(code)
  if (wantsWorldInteractions && (!hasSpatialCheck || !hasDomainAction)) {
    missing.push('collecte/scan/docking relies a des tests spatiaux, pas seulement a du texte HUD')
  }

  const wantsDynamicHud = /\b(hud|energy|energie|shield|fuel|minerals|resources|mission|score|cargo|inventory)\b/i.test(promptLower)
    || wantsWorldInteractions
  const hasDynamicHud = /\bset(?:Energy|Fuel|Shield|Minerals|Resources|Score|Mission|Cargo|Inventory)\s*\(|useReducer\s*\(|dispatch\s*\(/.test(code)
  if (wantsDynamicHud && wantsWorldInteractions && !hasDynamicHud) {
    missing.push('HUD dynamique mis a jour par les interactions')
  }
  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  return {
    ok: false,
    missing,
    hint: [
      'FIDELITE 3D INTERACTIVE INSUFFISANTE - la scene compile peut-etre, mais elle ne realise pas le brief.',
      ...missing.map((item) => `- ${item}`),
      '',
      'Correction attendue:',
      "- ajouter un etat de vaisseau/joueur (position, velocity, fuel/energy, cargo) pilote par keydown/keyup et useFrame(delta) ;",
      '- afficher une minimap/radar derivee des positions reelles des objets si le brief la demande ;',
      '- implementer scan/collect/docking avec distanceTo, raycaster, collision ou volumes 3D ;',
      '- connecter ces interactions au HUD et aux objectifs de mission ;',
      '- garder le rendu React Three Fiber propre, avec HUD HTML hors Canvas ou via Html de drei.',
    ].join('\n'),
  }
}
