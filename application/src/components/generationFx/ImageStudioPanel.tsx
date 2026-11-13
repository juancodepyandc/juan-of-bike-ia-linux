/**
 * Panneau central de l'écran de génération Image : chambre de diffusion WebGL
 * (chargée à la demande) et instruments réels autour d'elle.
 *
 * Chaque valeur affichée est mesurée ou lue dans la demande :
 *  - sujet verrouillé (objet, forme, texte exact, « aucune personne ») = même
 *    analyse que celle qui construit le prompt FLUX.2 ;
 *  - pipeline : sous-étapes réellement exécutées par ComfyUI, avec leur durée
 *    observée ; une sous-étape absente du graphe (super-résolution) reste grise ;
 *  - pas k/N, durée médiane mesurée d'un pas, temps restant de la diffusion
 *    calculé sur ces seules mesures ;
 *  - courbe de bruit du planificateur au pas réel (approximation affichée comme telle) ;
 *  - présence ou absence d'aperçus latents envoyés par le serveur.
 */
import { Suspense, lazy, useMemo } from 'react'
import { analyzeSubjectFidelity } from '../../services/imageSubjectFidelity.ts'
import { readComfyLive } from './comfyProgress.ts'
import { IMAGE_PIPELINE, fluxSigmaAt as sigmaAt, medianStepSeconds } from './comfyStages.ts'

const DiffusionStage = lazy(() => import('./DiffusionStage.tsx'))

const MONO = "'Cascadia Code',Consolas,monospace"

function hexA(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}

function fmtSec(ms: number) {
  const s = ms / 1000
  return s < 10 ? `${s.toFixed(1)} s` : s < 90 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, '0')}`
}


const SHAPE_FR: Record<string, string> = { heart: 'cœur', star: 'étoile', 'crescent moon': 'lune', round: 'rond', square: 'carré', teardrop: 'goutte', flower: 'fleur', diamond: 'diamant', spiral: 'spirale', oval: 'ovale', cloud: 'nuage', leaf: 'feuille' }

export type ImageStudioPanelProps = {
  accent: string
  prompt?: string
  aspect?: number
  refs?: { url: string; role: string }[]
  resultUrl?: string | null
  phaseIdx: number
  phaseCount: number
  startedAt: number
  readPulseAt: () => number
  done: boolean
  narrow: boolean
  /** dernières actions réellement journalisées par le module */
  logLines?: string[]
}

export default function ImageStudioPanel(props: ImageStudioPanelProps) {
  const { accent, prompt = '', narrow, done } = props
  const fidelity = useMemo(() => analyzeSubjectFidelity(prompt), [prompt])
  const subjectWords = useMemo(() => {
    const out: string[] = []
    const m = prompt.match(/\b(vases?|tasses?|mugs?|bols?|bagues?|colliers?|lampes?|bougies?|boites?|boîtes?|plaques?|gâteaux?|gateaux?|bouteilles?|flacons?|théières?|statues?|figurines?)\b/iu)
    if (m) out.push(m[1])
    return out
  }, [prompt])
  const live = readComfyLive()
  const own = live.module === 'image' && live.runAt >= props.startedAt - 1000
  const now = Date.now()
  const stepSec = own ? medianStepSeconds(live.stepTimes) : null
  const remainingDiff = own && stepSec != null && live.max > 0 && live.stage === 'sampling' ? (live.max - live.step) * stepSec : null
  const quality: 'high' | 'low' = narrow || (typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches) ? 'low' : 'high'

  const chips: Array<{ k: string; v: string; col: string }> = []
  if (fidelity.nounEn) {
    const shape = fidelity.shapeEn ? ` en forme de ${SHAPE_FR[fidelity.shapeEn] ?? fidelity.shapeEn}` : fidelity.shapeFr ? ` en forme de ${fidelity.shapeFr}` : ''
    chips.push({ k: 'SUJET', v: `${subjectWords[0] ?? fidelity.nounEn}${shape}`, col: accent })
  }
  for (const t of fidelity.inscriptions) chips.push({ k: 'TEXTE EXACT', v: `« ${t} »`, col: '#F5C451' })
  if (fidelity.objectOnly) chips.push({ k: 'VERROU', v: 'aucune personne · aucun animal', col: '#4ADE80' })

  const curIdx = own ? IMAGE_PIPELINE.findIndex((s) => s.stages.includes(live.stage)) : -1
  const sigma = own && live.stage === 'sampling' ? sigmaAt(live.step, live.max) : own && curIdx > 3 ? 0 : 1

  // courbe de bruit (planificateur à décalage, approximation) et position réelle
  const curve = useMemo(() => {
    const pts: string[] = []
    for (let i = 0; i <= 40; i++) pts.push(`${(i / 40) * 100},${sigmaAt(i, 40) * 36 + 2}`)
    return pts.join(' ')
  }, [])
  const markerX = own && live.max ? (live.step / live.max) * 100 : 0

  const pipeline = (
    <div style={{
      display: 'flex', flexDirection: narrow ? 'row' : 'column', gap: narrow ? 4 : 6, overflowX: narrow ? 'auto' : undefined,
      fontFamily: MONO, fontSize: 10.5,
    }}>
      {!narrow && <span style={{ fontSize: 9.5, letterSpacing: '.22em', color: '#8B93A7' }}>PIPELINE RÉEL COMFYUI</span>}
      {IMAGE_PIPELINE.map((st, i) => {
        // téléphone : la rangée commence à la sous-étape précédant celle en cours
        if (narrow && curIdx > 1 && i < curIdx - 1 && !done) return null
        const times = st.stages.map((s) => live.stageTimes[s]).filter(Boolean) as { start: number; end?: number }[]
        const seen = own && times.length > 0
        const current = own && i === curIdx && !done
        // une sous-étape absente du graphe (super-résolution non demandée) n'est jamais marquée faite
        const finished = seen && !current
        const skipped = done && !seen
        const startT = seen ? Math.min(...times.map((x) => x.start)) : 0
        const endT = seen ? (current ? now : Math.max(...times.map((x) => x.end ?? now))) : 0
        const col = current ? accent : finished ? '#4ADE80' : '#4B5563'
        const extra = st.stages.includes('sampling') && own && live.max ? ` ${live.step}/${live.max}` : st.stages.includes('upscale') && own && live.subMax ? ` ${live.subStep}/${live.subMax}` : ''
        return (
          <div key={st.label} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: narrow ? '4px 8px' : '5px 9px', borderRadius: 8, whiteSpace: 'nowrap',
            border: `1px solid ${current ? accent : finished ? 'rgba(74,222,128,.3)' : 'rgba(255,255,255,.06)'}`,
            background: current ? hexA(accent, 0.14) : 'rgba(4,6,11,.55)',
            boxShadow: current ? `0 0 14px ${hexA(accent, 0.35)}` : 'none', color: current ? '#fff' : finished ? '#B7F7CC' : '#6B7280',
          }}>
            <span style={{ width: 7, height: 7, borderRadius: 999, background: col, boxShadow: current ? `0 0 8px ${accent}` : 'none', flex: 'none' }} />
            <span style={{ flex: 1 }}>{st.label}{extra}</span>
            {seen && <span style={{ color: '#8B93A7' }}>{fmtSec(Math.max(0, endT - startT))}</span>}
            {skipped && <span style={{ color: '#4B5563' }}>non exécutée</span>}
          </div>
        )
      })}
    </div>
  )

  return (
    <div style={{
      position: 'absolute',
      // à droite, la colonne reste libre pour le personnage posé au-dessus du HUD
      left: narrow ? 12 : 48, right: narrow ? 12 : 232,
      top: narrow ? 66 : 60, bottom: narrow ? 236 : 190,
      display: 'flex', flexDirection: narrow ? 'column-reverse' : 'row-reverse', gap: 14, pointerEvents: 'auto',
    }}>
      <div style={{ position: 'relative', flex: 1, minWidth: 0, minHeight: 180, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, letterSpacing: '.24em', color: '#8B93A7', fontFamily: MONO }}>
            {done ? 'IMAGE PRÊTE — RÉVÉLÉE DEPUIS LE RENDU RÉEL' : own ? `CHAMBRE DE DIFFUSION FLUX.2 — ${live.label.toUpperCase()}` : 'CHAMBRE DE DIFFUSION FLUX.2 — PRÉPARATION DE LA DEMANDE'}
          </span>
          <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {chips.map((c) => (
              <span key={c.k + c.v} style={{
                fontSize: 10, padding: '4px 10px', borderRadius: 999, border: `1px solid ${hexA(c.col, 0.5)}`,
                color: '#E6EAF5', background: 'rgba(4,6,11,.7)', fontFamily: MONO, whiteSpace: 'nowrap',
              }}><b style={{ color: c.col }}>{c.k}</b> {c.v}</span>
            ))}
          </span>
        </div>
        <div style={{
          position: 'relative', flex: 1, minHeight: 160, borderRadius: 16, overflow: 'hidden',
          border: `1px solid ${hexA(accent, 0.22)}`,
          background: `radial-gradient(ellipse at 50% 55%, ${hexA(accent, 0.1)}, rgba(3,5,10,.94) 65%)`,
        }}>
          <Suspense fallback={<div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#5A6377', fontSize: 11 }}>Initialisation de la chambre de diffusion…</div>}>
            <DiffusionStage
              accent={accent}
              phaseIdx={props.phaseIdx}
              phaseCount={props.phaseCount}
              readPulseAt={props.readPulseAt}
              prompt={prompt}
              subjectWords={subjectWords}
              inscriptionWords={fidelity.inscriptions}
              aspect={props.aspect}
              sessionStartedAt={props.startedAt}
              refs={props.refs}
              resultUrl={props.resultUrl}
              done={done}
              quality={quality}
            />
          </Suspense>
          {done && (
            <div style={{
              position: 'absolute', left: '50%', top: 14, transform: 'translateX(-50%)', padding: '6px 14px', borderRadius: 999,
              fontSize: 12, letterSpacing: '.2em', color: '#4ADE80', border: '1px solid rgba(74,222,128,.5)', background: 'rgba(4,10,8,.75)',
              fontFamily: MONO,
            }}>✓ IMAGE PRÊTE</div>
          )}
          <div style={{
            position: 'absolute', left: 12, right: 12, bottom: 10, display: 'flex', justifyContent: 'space-between', gap: 10,
            fontSize: 10.5, color: '#B7C0D4', fontFamily: MONO, pointerEvents: 'none', textShadow: '0 1px 6px #000', flexWrap: 'wrap',
          }}>
            <span>
              {own && live.max ? `pas ${live.step}/${live.max}` : 'pas —'}
              {stepSec != null ? ` · ${stepSec.toFixed(2)} s/pas mesuré` : ''}
              {remainingDiff != null ? ` · diffusion restante ≈ ${fmtSec(remainingDiff * 1000)}` : ''}
            </span>
            <span style={{ color: own && live.previewCount ? '#4ADE80' : '#7C869C' }}>
              {own && live.previewCount
                ? `aperçu latent réel · ${live.previewCount} trame(s)`
                : 'aperçu latent non transmis par ComfyUI'}
            </span>
          </div>
        </div>
      </div>
      {!narrow ? (
        <div style={{ width: 236, flex: 'none', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {pipeline}
          <div style={{ borderRadius: 10, border: '1px solid rgba(255,255,255,.07)', background: 'rgba(0,0,0,.32)', padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.2em', color: '#8B93A7', fontFamily: MONO, marginBottom: 4 }}>
              BRUIT σ {own && live.stage === 'sampling' ? sigma.toFixed(2) : ''}
            </div>
            <svg viewBox="0 0 100 40" width="100%" height="56" preserveAspectRatio="none" aria-hidden="true">
              <polyline points={curve} fill="none" stroke={hexA(accent, 0.55)} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
              {own && live.max > 0 && (
                <>
                  <line x1={markerX} x2={markerX} y1="0" y2="40" stroke="#fff" strokeOpacity=".35" strokeWidth="1" vectorEffect="non-scaling-stroke" />
                  <circle cx={markerX} cy={sigma * 36 + 2} r="2.2" fill={accent} />
                </>
              )}
            </svg>
            <div style={{ fontSize: 9, color: '#6B7280', fontFamily: MONO }}>courbe du planificateur (approx.) · position = pas réel reçu</div>
          </div>
          <div style={{
            flex: 1, minHeight: 0, overflow: 'hidden', borderRadius: 10, border: '1px solid rgba(255,255,255,.07)',
            background: 'rgba(0,0,0,.32)', padding: '8px 10px', fontFamily: MONO, fontSize: 10, lineHeight: 1.6, color: '#9AA5BC',
            display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
          }}>
            {(props.logLines ?? []).slice(-5).map((l, i, arr) => (
              <div key={i} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: i === arr.length - 1 ? '#E6EAF5' : undefined }}>
                <span style={{ color: accent }}>›</span> {l}
              </div>
            ))}
            {!(props.logLines ?? []).length && <div style={{ color: '#5A6377' }}>chaque action réelle du module s’affichera ici…</div>}
          </div>
        </div>
      ) : (
        <div style={{ flex: 'none' }}>{pipeline}</div>
      )}
    </div>
  )
}
