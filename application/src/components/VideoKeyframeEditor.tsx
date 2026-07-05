/**
 * VideoKeyframeEditor — minimalist timeline for chaining motion prompts.
 *
 * Each keyframe is a prompt + time + seed, and the player builds an array
 * the Wan 2.2 backend can pipeline (T2V of first frame, then I2V hops).
 * Pure UI for now — the Video module wires it to `createWanWorkflow()`.
 */
import { useState } from 'react'

export interface Keyframe {
  id: string
  time: number     // seconds from start
  prompt: string
  seed?: number
  motion?: 'static' | 'zoom' | 'pan' | 'rotate' | 'shake'
}

interface Props {
  value: Keyframe[]
  onChange: (next: Keyframe[]) => void
  /** Total video length in seconds. */
  duration?: number
  onDurationChange?: (sec: number) => void
}

const MOTIONS: Array<NonNullable<Keyframe['motion']>> = ['static', 'zoom', 'pan', 'rotate', 'shake']

export default function VideoKeyframeEditor({ value, onChange, duration = 8, onDurationChange }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(value[0]?.id ?? null)

  const add = () => {
    const id = `kf-${Date.now().toString(36)}`
    const maxT = value.reduce((m, k) => Math.max(m, k.time), 0)
    const next: Keyframe = {
      id,
      time: Math.min(duration, maxT + (duration / 4)),
      prompt: '',
      motion: 'static',
    }
    onChange([...value, next].sort((a, b) => a.time - b.time))
    setSelectedId(id)
  }
  const patch = (id: string, update: Partial<Keyframe>) => {
    onChange(value.map((k) => (k.id === id ? { ...k, ...update } : k)).sort((a, b) => a.time - b.time))
  }
  const remove = (id: string) => {
    onChange(value.filter((k) => k.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  const selected = value.find((k) => k.id === selectedId)

  return (
    <div className="vke">
      <div className="vke-head">
        <span className="vke-label">Keyframes · {value.length}</span>
        <label className="vke-duration">
          Durée
          <input type="number" min={2} max={60} value={duration}
            onChange={(e) => onDurationChange?.(Math.max(2, Math.min(60, Number(e.target.value) || 8)))} />
          <span>s</span>
        </label>
        <button type="button" className="vke-add" onClick={add}>+ keyframe</button>
      </div>

      <div className="vke-timeline" role="group" aria-label="Timeline">
        <div className="vke-timeline-track">
          {Array.from({ length: Math.floor(duration) + 1 }).map((_, i) => (
            <span key={i} className="vke-tick" style={{ left: `${(i / duration) * 100}%` }}>
              <span>{i}s</span>
            </span>
          ))}
          {value.map((k) => (
            <button
              key={k.id}
              type="button"
              className={`vke-pin ${selectedId === k.id ? 'is-sel' : ''}`}
              style={{ left: `${(k.time / duration) * 100}%` }}
              onClick={() => setSelectedId(k.id)}
              title={`${k.time.toFixed(1)}s · ${k.motion || 'static'}`}>
              <span className="vke-pin-dot" />
              <span className="vke-pin-label">{k.prompt.slice(0, 18) || '(vide)'}</span>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="vke-editor">
          <div className="vke-editor-row">
            <label>Temps</label>
            <input type="number" step="0.5" min={0} max={duration} value={selected.time}
              onChange={(e) => patch(selected.id, { time: Math.max(0, Math.min(duration, Number(e.target.value) || 0)) })} />
            <span>s / {duration}s</span>
          </div>
          <div className="vke-editor-row">
            <label>Prompt</label>
            <input type="text" placeholder="décris ce plan…"
              value={selected.prompt}
              onChange={(e) => patch(selected.id, { prompt: e.target.value })} />
          </div>
          <div className="vke-editor-row">
            <label>Motion</label>
            {MOTIONS.map((m) => (
              <button key={m} type="button"
                className={`vke-motion ${selected.motion === m ? 'is-active' : ''}`}
                onClick={() => patch(selected.id, { motion: m })}>
                {m}
              </button>
            ))}
          </div>
          <div className="vke-editor-row">
            <label>Seed</label>
            <input type="number" value={selected.seed ?? ''}
              placeholder="aléatoire"
              onChange={(e) => patch(selected.id, { seed: e.target.value ? Number(e.target.value) : undefined })} />
            <button type="button" className="vke-del" onClick={() => remove(selected.id)}>🗑 retirer</button>
          </div>
        </div>
      )}
    </div>
  )
}
