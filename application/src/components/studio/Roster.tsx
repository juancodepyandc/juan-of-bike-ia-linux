// Studio Roster — 7 personae illustrés (Sage / Lou / Mira / Diego / Tess / Sam / Yann).
// Chaque portrait respire (blink + breathing + head-turn + saccade + cheek-flush) en boucle.
// Cliquer un portrait route vers le module métier correspondant (chat, code, image, voix, etc.).
import React from 'react'
// @ts-ignore - studio avatars is a ported JS-loose module
import { Avatar, P } from './avatars.tsx'
import { useAppStore } from '../../stores/appStore.ts'
import type { ModuleId } from '../../types/app.ts'

export type Persona = 'sage' | 'lou' | 'mira' | 'diego' | 'tess' | 'sam' | 'yann'

// Each persona maps to (a) the activeModule that should be selected for the
// downstream desktop module screen, and (b) the mobile grimoire page where
// that capability is reachable. The mobile shell expects the second so a tap
// on a portrait jumps the swipe pager to the right chapter.
export type PersonaPageId = 'home' | 'team' | 'chat' | 'create' | 'academy' | 'gallery' | 'canvas'

const PERSONA_TO_MODULE: Record<Persona, { module: ModuleId; page: PersonaPageId; label: string; sub: string }> = {
  sage:  { module: 'conversation', page: 'chat',    label: 'Sage',  sub: 'Orchestratrice · pipeline 6 étapes' },
  lou:   { module: 'code',         page: 'create',  label: 'Lou',   sub: 'Codeur · sandbox 22 langues' },
  mira:  { module: 'image',        page: 'create',  label: 'Mira',  sub: 'Atelier · FLUX 15 styles' },
  diego: { module: 'voice',        page: 'chat',    label: 'Diego', sub: 'Voix · Voxtral + Kokoro' },
  tess:  { module: 'video',        page: 'create',  label: 'Tess',  sub: 'Cinéma · Wan2.2 + MuseTalk' },
  sam:   { module: 'learning',     page: 'academy', label: 'Sam',   sub: 'Académie · BAC + Anki' },
  yann:  { module: '3d',           page: 'create',  label: 'Yann',  sub: 'Forge 3D · Hunyuan + rescue' },
}

const PERSONAE: Persona[] = ['sage', 'lou', 'mira', 'diego', 'tess', 'sam', 'yann']

interface StudioRosterProps {
  /** Mobile grimoire passes this so a portrait tap turns the page directly. */
  onPick?: (persona: Persona, page: PersonaPageId, module: ModuleId) => void
}

export default function StudioRoster({ onPick }: StudioRosterProps = {}) {
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  return (
    <div style={{
      width: '100%', minHeight: '100%', padding: '24px 16px 96px',
      background: 'linear-gradient(180deg, #1a1612 0%, #2a1f18 100%)',
      color: '#fbf6e8', fontFamily: '"Geist", "Inter", system-ui, sans-serif',
      overflowY: 'auto',
    }}>
      <div style={{ marginBottom: 24, padding: '8px 4px' }}>
        <h1 style={{
          fontFamily: '"Instrument Serif", serif',
          fontSize: 'clamp(28px, 7vw, 44px)',
          fontWeight: 400,
          margin: 0,
          letterSpacing: '-0.02em',
          background: 'linear-gradient(135deg, #ffd040 0%, #c89570 50%, #a82a3a 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          L'équipe
        </h1>
        <p style={{
          fontFamily: '"Caveat", "Brush Script MT", cursive',
          fontSize: 'clamp(14px, 4vw, 20px)',
          color: '#ffd040', margin: '4px 0 0',
        }}>
          7 personae qui respirent · tape pour entrer dans son module
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 14,
      }}>
        {PERSONAE.map((persona) => {
          const meta = PERSONA_TO_MODULE[persona]
          // @ts-ignore loose module access
          const data = (P && P[persona]) || {}
          return (
            <button
              key={persona}
              onClick={() => {
                setActiveModule(meta.module)
                onPick?.(persona, meta.page, meta.module)
              }}
              style={{
                position: 'relative',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: '12px 8px 10px',
                border: 'none', borderRadius: 16,
                background: `linear-gradient(160deg, ${data.clothBase || '#3a2a1a'}22 0%, transparent 70%), rgba(20,16,12,0.6)`,
                color: '#fbf6e8',
                cursor: 'pointer',
                boxShadow: '0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
                transition: 'transform 0.18s cubic-bezier(.4,0,.2,1), box-shadow 0.18s',
                font: 'inherit',
              }}
              onTouchStart={(e) => { (e.currentTarget as HTMLElement).style.transform = 'scale(.97)' }}
              onTouchEnd={(e) => { (e.currentTarget as HTMLElement).style.transform = '' }}
            >
              <div style={{ width: '100%', aspectRatio: '0.66', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Avatar
                  persona={persona}
                  mood="neutral"
                  gesture="idle"
                  w={140}
                  h={210}
                  light={{ color: '#ffd09a', dir: 'right', intensity: 0.28 }}
                />
              </div>
              <div style={{
                marginTop: 4, fontFamily: '"Instrument Serif", serif',
                fontSize: 18, fontWeight: 500, color: '#fbf6e8', letterSpacing: '-0.01em',
              }}>{meta.label}</div>
              <div style={{
                fontSize: 10, color: data.accent || '#a89070',
                fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                letterSpacing: '0.08em', marginTop: 1, textTransform: 'uppercase',
              }}>{meta.sub.split(' · ')[0]}</div>
            </button>
          )
        })}
      </div>

      <div style={{
        marginTop: 28, padding: '14px 16px',
        borderRadius: 12,
        background: 'rgba(255, 208, 64, 0.08)',
        border: '1px solid rgba(255, 208, 64, 0.25)',
      }}>
        <div style={{
          fontFamily: '"JetBrains Mono", ui-monospace, monospace',
          fontSize: 10, letterSpacing: '0.12em', color: '#ffd040', marginBottom: 6,
        }}>
          ANATOMIE · 35+ ÉLÉMENTS SVG · 40 KEYFRAMES PIXAR
        </div>
        <div style={{ fontSize: 12.5, color: '#d8c8b0', lineHeight: 1.5 }}>
          Sclère + iris gradient 4 stops · double cils · sourcils Bezier 6 points ·
          nez avec narines + reflet · lèvres haut/bas + dents · oreilles hélix complètes ·
          12-18 mèches cheveux · vêtements signatures (manteau · hoodie · tablier · blazer · etc.).
          Anticipation + follow-through + secondary motion appliqués en boucle.
        </div>
      </div>
    </div>
  )
}
