/**
 * RigEditor — inline editor for a Forge rig plan produced by the Ollama step.
 *
 * Lets the user review and tweak the layers before SAM2 segmentation :
 *   - rename a layer id     (e.g. "star_eye" → "left_gem")
 *   - reorder by dragging   (z-order)
 *   - toggle kind           (static / blink / float_and_contract / …)
 *   - edit the GroundingDINO prompt hint for each layer
 *   - add / remove a layer
 *
 * The component is controlled : `value` is a RigPlan, `onChange` fires on
 * every mutation so the parent persists the update to the queue artifacts
 * and the next segmentation step uses the new rig.
 */
import { useState } from 'react'
import type { RigLayer, RigPlan } from '../services/characterForge'

const KIND_OPTIONS: Array<RigLayer['kind']> = [
  'static',
  'blink_eyelid',
  'brow_raise',
  'phonemes',
  'float_and_contract',
  'float_and_rotate',
  'rigid_swing',
  'hair_sway',
  'fx_triggered',
  'custom',
]

interface Props {
  value: RigPlan
  onChange: (next: RigPlan) => void
  /** Optional map of per-layer prompt overrides (layer.id → text) */
  promptOverrides?: Record<string, string>
  onPromptOverride?: (layerId: string, prompt: string) => void
}

export default function RigEditor({ value, onChange, promptOverrides = {}, onPromptOverride }: Props) {
  const [dragFrom, setDragFrom] = useState<number | null>(null)

  const patchLayer = (idx: number, patch: Partial<RigLayer>) => {
    const layers = value.layers.map((l, i) => (i === idx ? { ...l, ...patch } : l))
    onChange({ ...value, layers })
  }
  const removeLayer = (idx: number) => {
    const layers = value.layers.filter((_, i) => i !== idx)
    onChange({ ...value, layers })
  }
  const addLayer = () => {
    const maxZ = value.layers.reduce((m, l) => Math.max(m, l.z ?? 0), 0)
    onChange({
      ...value,
      layers: [...value.layers, { id: `layer_${value.layers.length + 1}`, z: maxZ + 1, kind: 'static' }],
    })
  }
  const moveLayer = (from: number, to: number) => {
    if (from === to) return
    const layers = value.layers.slice()
    const [m] = layers.splice(from, 1)
    layers.splice(to, 0, m)
    // Renumber z to reflect new order (0..n-1)
    const renumbered = layers.map((l, i) => ({ ...l, z: i }))
    onChange({ ...value, layers: renumbered })
  }

  return (
    <div className="rig-editor">
      <div className="rig-editor-head">
        <div className="rig-editor-title">Édition du rig</div>
        <span className="rig-editor-count">{value.layers.length} calques · {value.layers.filter((l) => l.kind !== 'static').length} animés</span>
        <button type="button" className="rig-editor-add" onClick={addLayer}>+ calque</button>
      </div>
      <div className="rig-editor-list">
        {value.layers.map((layer, i) => (
          <div
            key={`${layer.id}-${i}`}
            draggable
            onDragStart={() => setDragFrom(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => { if (dragFrom !== null) moveLayer(dragFrom, i); setDragFrom(null) }}
            className={`rig-editor-row ${dragFrom === i ? 'is-dragging' : ''}`}>
            <span className="rig-editor-handle" title="Glisser pour réordonner">⋮⋮</span>
            <span className="rig-editor-z">z={layer.z}</span>
            <input
              type="text"
              value={layer.id}
              onChange={(e) => patchLayer(i, { id: e.target.value.replace(/\s+/g, '_') })}
              className="rig-editor-id"
              spellCheck={false}
            />
            <select
              value={layer.kind}
              onChange={(e) => patchLayer(i, { kind: e.target.value as RigLayer['kind'] })}
              className="rig-editor-kind">
              {KIND_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            {onPromptOverride && layer.kind !== 'static' && (
              <input
                type="text"
                value={promptOverrides[layer.id] || ''}
                onChange={(e) => onPromptOverride(layer.id, e.target.value)}
                placeholder="prompt GroundingDINO (vide = heuristique)"
                className="rig-editor-prompt"
              />
            )}
            <button type="button" className="rig-editor-del" onClick={() => removeLayer(i)} title="Supprimer">×</button>
          </div>
        ))}
      </div>
      {value.forbidden && value.forbidden.length > 0 && (
        <div className="rig-editor-forbidden">
          Interdits : {value.forbidden.map((f) => <span key={f} className="rig-editor-forbidden-chip">{f}</span>)}
        </div>
      )}
    </div>
  )
}
