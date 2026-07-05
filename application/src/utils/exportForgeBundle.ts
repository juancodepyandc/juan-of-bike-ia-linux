/**
 * exportForgeBundle — package a full Forge character as a single ZIP.
 *
 * Contains :
 *   meta.json       — CharacterMeta (id, display_name, franchise, style)
 *   traits.json     — signature + forbidden_elements
 *   rig.json        — layer order, kinds, anim_rules
 *   portrait.png    — the canonical reference
 *   base_inpaint.png (optional) — LaMa-cleaned base
 *   layers/         — per-layer PNG extracted by SAM2 + BiRefNet
 *   README.md       — quick doc so the user knows what they're sharing
 *
 * Relies on JSZip (already in dependencies). Fetches each URL through the
 * browser so this works in Tauri AND in cloud mode.
 */
import JSZip from 'jszip'
import type { ForgeResult } from '../services/characterForge'

async function fetchToUint8(url: string): Promise<Uint8Array | null> {
  try {
    const r = await fetch(url, { cache: 'no-store' })
    if (!r.ok) return null
    const b = await r.arrayBuffer()
    return new Uint8Array(b)
  } catch { return null }
}

function slug(s: string): string {
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'character'
}

export async function exportForgeBundle(result: ForgeResult): Promise<Blob> {
  const zip = new JSZip()
  const name = slug(result.meta.display_name || result.meta.id)

  zip.file('meta.json',   JSON.stringify(result.meta,   null, 2))
  zip.file('traits.json', JSON.stringify(result.traits, null, 2))
  zip.file('rig.json',    JSON.stringify(result.rig,    null, 2))
  if (result.researchBrief) zip.file('research_brief.md', result.researchBrief)
  if (result.howTheySpeak)   zip.file('how_they_speak.md', result.howTheySpeak)

  // Portrait reference
  const portrait = await fetchToUint8(result.portraitUrl)
  if (portrait) zip.file('portrait.png', portrait)

  // Inpainted base layer
  if (result.baseLayerUrl) {
    const base = await fetchToUint8(result.baseLayerUrl)
    if (base) zip.file('base_inpainted.png', base)
  }

  // Individual layers
  if (result.layerFiles?.length) {
    const layersFolder = zip.folder('layers')!
    for (const layer of result.layerFiles) {
      const bytes = await fetchToUint8(layer.url)
      if (!bytes) continue
      const filename = `${slug(layer.layerId)}.png`
      layersFolder.file(filename, bytes)
    }
    // Index
    layersFolder.file('index.json', JSON.stringify(
      result.layerFiles.map((l) => ({ layerId: l.layerId, file: `${slug(l.layerId)}.png`, prompt: l.prompt })),
      null, 2,
    ))
  }

  // README
  const readme = [
    `# ${result.meta.display_name}`,
    ``,
    result.meta.franchise ? `> ${result.meta.franchise}${result.meta.creator ? ` · ${result.meta.creator}` : ''}` : '',
    ``,
    '## Structure',
    '- `meta.json` · identifiant + franchise + style + router_model',
    '- `traits.json` · features signature + éléments interdits',
    '- `rig.json` · layers (z-order, kind), anim_rules',
    '- `portrait.png` · image de référence canonique',
    result.baseLayerUrl ? '- `base_inpainted.png` · portrait avec régions animées inpaintées (LaMa)' : '',
    result.layerFiles?.length ? `- \`layers/\` · ${result.layerFiles.length} PNG extraits (SAM2 + BiRefNet)` : '',
    '',
    '## Relecture',
    'Utilise ce bundle pour rejouer le personnage dans juan of bike IA ou',
    "le charger dans un Live2D / Spine en mappant les kinds `float_and_contract`",
    '/ `blink_eyelid` / `phonemes` vers tes propres animations.',
    '',
    `Exporté depuis juan of bike IA — ${new Date().toISOString()}`,
  ].filter(Boolean).join('\n')
  zip.file('README.md', readme)

  const blob = await zip.generateAsync({ type: 'blob' })
  return blob
}

export async function downloadForgeBundle(result: ForgeResult): Promise<void> {
  const blob = await exportForgeBundle(result)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `character_${slug(result.meta.display_name || result.meta.id)}.zip`
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
