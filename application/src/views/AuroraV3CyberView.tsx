/**
 * AuroraV3CyberView — Ricochet "DEFCON 3 / Mr. Robot" port.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-5.jsx
 * (CyberV3): blood-on-black palette, pulsing alert banner, threat
 * matrix sidebar with severity colour-codes (CRIT/HIGH/OK), terminal
 * lab in centre, leaderboard + ops sidebar, secure log footer.
 * Real wiring through useCyberViewLogic — every Manga feature kept:
 * 8 katas, XP/belt, lab forge + evolve, postMessage auto-validation,
 * grading, deep hints, multi-stage, leaderboard recording.
 */
import { useEffect, useState } from 'react'
import { useCyberViewLogic } from '../hooks/useCyberViewLogic'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
import VoicePushToTalk from '../components/VoicePushToTalk'

const RED = '#ff4a4a'
const RED_DIM = '#cc8c8c'
const RED_BG = '#0a0204'
const RED_BORDER = '#5a1414'
const GREEN = '#7df9c4'
const AMBER = '#ffb947'
const RED_DARK = '#400808'
const PINK = '#ff8080'
const TERMINAL_BG = '#1a0408'

function AlertBtn({ children, onClick, disabled, primary }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; primary?: boolean
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      style={{
        background: primary ? RED : 'transparent',
        color: primary ? RED_BG : RED,
        border: `1px solid ${RED}`,
        padding: '6px 10px',
        fontFamily: 'inherit', fontSize: 10, letterSpacing: '0.2em',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
      }}>
      [{children}]
    </button>
  )
}

export default function AuroraV3CyberView() {
  const C = useCyberViewLogic()
  const [t, setT] = useState(0)
  // v82eb : drag-drop parity V3 — fichier(s) → uploadNotesMulti
  const drop = useFileDrop({
    onFiles: (files) => void C.uploadNotesMulti(files),
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: C.notesUploading,
  })
  useEffect(() => {
    let r = 0
    const l = () => { setT(performance.now() / 1000); r = requestAnimationFrame(l) }
    r = requestAnimationFrame(l)
    return () => cancelAnimationFrame(r)
  }, [])

  const defcon = C.active.difficulty === 3 ? 1 : C.active.difficulty === 2 ? 3 : 5
  const progressBars = C.lab
    ? Math.round(20 + Math.sin(t * 2) * 5)
    : 0

  return (
    <div {...drop.bind} style={{
      width: '100%', height: '100%', background: RED_BG,
      color: RED, fontFamily: 'Space Mono, JetBrains Mono, monospace', fontSize: 12,
      padding: 18,
      display: 'grid',
      gridTemplateColumns: '260px 1fr 280px',
      gridTemplateRows: '36px 1fr 100px',
      gap: 12,
      position: 'relative', overflow: 'hidden',
      outline: drop.isDraggingOver ? `2px dashed ${RED}` : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
    }}>
      {/* Alert bar */}
      <header style={{
        gridColumn: '1 / -1',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: RED_DARK, border: `1px solid ${RED}`, padding: '6px 14px',
        letterSpacing: '0.3em',
      }}>
        <span style={{ animation: 'pulse 1.2s ease-in-out infinite' }}>
          ◢ DEFCON {defcon} ◣  KATA · {C.active.name.toUpperCase()}  ◢ {C.lab ? 'ARMED' : 'STANDBY'} ◣
        </span>
        <span style={{ color: AMBER }}>{new Date().toISOString().slice(11, 19)}Z</span>
      </header>

      {/* Threat matrix sidebar */}
      <aside style={{ border: `1px solid ${RED_BORDER}`, padding: 10, overflowY: 'auto' }}>
        <div style={{ color: PINK, fontSize: 10, letterSpacing: '0.2em', marginBottom: 8 }}>// KATA.MATRIX</div>
        {C.KATAS.map((k) => {
          const active = k.id === C.activeId
          const lvl = k.difficulty === 3 ? 'CRIT' : k.difficulty === 2 ? 'HIGH' : 'OK'
          const lvlColor = lvl === 'OK' ? GREEN : lvl === 'HIGH' ? AMBER : RED
          return (
            <button key={k.id} type="button" onClick={() => C.setActiveKata(k.id)}
              style={{
                display: 'grid', gridTemplateColumns: '70px 1fr 50px',
                width: '100%', textAlign: 'left',
                padding: '5px 4px', borderBottom: `1px dashed ${RED_BORDER}`,
                fontSize: 11, background: active ? RED_DARK : 'transparent',
                color: 'inherit', border: 'none', cursor: 'pointer',
                fontFamily: 'inherit',
              }}>
              <span style={{ color: PINK }}>{k.id.toUpperCase().slice(0, 6)}</span>
              <span style={{ color: RED_DIM, fontStyle: 'italic' }}>{k.discipline}</span>
              <span style={{ color: lvlColor, textAlign: 'right' }}>{lvl}</span>
            </button>
          )
        })}
        <div style={{ marginTop: 14, color: PINK, fontSize: 10, letterSpacing: '0.2em' }}>// CORPUS</div>
        <div style={{ fontSize: 10, color: RED_DIM, marginTop: 6, lineHeight: 1.6 }}>
          rockyou.txt · 14 344 391<br/>
          common-passwd · 1M<br/>
          aurora.heur · custom<br/>
          XP · {C.xp} · ceinture {C.belt}
        </div>

        <div style={{ marginTop: 14, color: PINK, fontSize: 10, letterSpacing: '0.2em' }}>// STANCE</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
          <AlertBtn primary={C.stance === 'offense'} onClick={() => C.setStance('offense')}>OFF</AlertBtn>
          <AlertBtn primary={C.stance === 'defense'} onClick={() => C.setStance('defense')}>DEF</AlertBtn>
        </div>
      </aside>

      {/* Main terminal */}
      <main style={{
        border: `1px solid ${RED_BORDER}`, padding: 14, background: TERMINAL_BG,
        display: 'flex', flexDirection: 'column', minHeight: 0,
      }}>
        <div style={{
          color: PINK, fontSize: 10, letterSpacing: '0.2em', marginBottom: 8,
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>// DOJO.SESSION · 0x{C.activeId.toUpperCase()}-{String(C.stage).padStart(2, '0')}</span>
          <span style={{ color: AMBER }}>SCORE {C.xp} · BELT {C.belt.toUpperCase()}</span>
        </div>

        {C.lab ? (
          <>
            <div style={{ color: AMBER, fontSize: 11, marginBottom: 6 }}>
              ▸ LAB ARMED :: {C.lab.title}
            </div>
            {C.lab.briefing && (
              <div style={{ color: RED_DIM, fontSize: 11, marginBottom: 8, fontStyle: 'italic' }}>
                {C.lab.briefing}
              </div>
            )}
            <iframe
              key={`${C.lab.kataId}-${C.sandboxKey}`}
              title="Cyber lab"
              srcDoc={C.lab.html}
              sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
              style={{ flex: 1, width: '100%', border: `1px solid ${RED_BORDER}`, background: '#000', minHeight: 200 }}
            />
            {/* Objectives ribbon */}
            <div style={{ marginTop: 8, fontSize: 10, color: PINK, letterSpacing: '0.2em' }}>// OBJECTIVES</div>
            <div style={{ marginTop: 4, maxHeight: 120, overflowY: 'auto' }}>
              {C.lab.objectives.map((obj) => {
                const done = C.doneObjectives.has(obj.id)
                return (
                  <div key={obj.id} style={{
                    display: 'flex', gap: 6, padding: '3px 0', fontSize: 11,
                    color: done ? GREEN : RED_DIM,
                    textDecoration: done ? 'line-through' : 'none',
                  }}>
                    <button type="button" onClick={() => C.toggleObjective(obj.id)}
                      style={{
                        width: 14, height: 14, flexShrink: 0,
                        background: done ? GREEN : 'transparent',
                        border: `1px solid ${done ? GREEN : RED}`,
                        cursor: 'pointer', color: '#000', fontSize: 9, padding: 0,
                      }}>{done ? '✓' : ''}</button>
                    <span style={{ flex: 1 }}>► {obj.text}</span>
                    <button type="button"
                      onClick={() => C.setGraderFor(C.graderFor === obj.id ? null : obj.id)}
                      style={{
                        background: 'transparent', border: `1px solid ${AMBER}`, color: AMBER,
                        padding: '0 6px', fontSize: 9, cursor: 'pointer',
                      }}>VALIDATE</button>
                    {[1, 2, 3].map((lvl) => {
                      const taken = (C.deepHints[obj.id] || []).some((h) => h.level === lvl)
                      return (
                        <button key={lvl} type="button"
                          disabled={!!C.deepHintBusy || taken}
                          onClick={() => void C.askDeepHint(obj, lvl as 1|2|3)}
                          style={{
                            background: taken ? AMBER : 'transparent', color: taken ? '#000' : RED_DIM,
                            border: `1px solid ${RED_BORDER}`, padding: '0 4px',
                            fontSize: 9, cursor: taken ? 'default' : 'pointer',
                          }}>HNT{lvl}</button>
                      )
                    })}
                  </div>
                )
              })}
            </div>
            {C.graderFor && (() => {
              const obj = C.lab!.objectives.find((o) => o.id === C.graderFor)
              if (!obj) return null
              return (
                <div style={{ marginTop: 4, padding: 6, border: `1px dashed ${RED_BORDER}`, background: RED_DARK }}>
                  <textarea rows={2}
                    value={C.graderAnswer[obj.id] || ''}
                    onChange={(e) => C.setGraderAnswer({ ...C.graderAnswer, [obj.id]: e.target.value })}
                    placeholder={obj.flag ? 'flag{...}' : 'answer...'}
                    style={{
                      width: '100%', background: '#000', color: RED, border: `1px solid ${RED_BORDER}`,
                      fontFamily: 'inherit', fontSize: 11, padding: 4, resize: 'vertical',
                    }} />
                  <AlertBtn onClick={() => void C.gradeCyberObjective(obj, (C.graderAnswer[obj.id] || '').trim())}
                    disabled={!!C.graderBusy || !(C.graderAnswer[obj.id] || '').trim()}>
                    {C.graderBusy === obj.id ? 'EVAL...' : 'EVAL'}
                  </AlertBtn>
                </div>
              )
            })()}
            {C.allDone && (
              <div style={{
                marginTop: 8, padding: 8, background: GREEN, color: '#000',
                fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                ✓ KATA RESOLVED · +{C.active.difficulty * 30} XP
                {C.stage < 4 && (
                  <button type="button" onClick={C.advanceStage}
                    style={{ background: '#000', color: GREEN, border: 'none', padding: '4px 10px', fontFamily: 'inherit', cursor: 'pointer' }}>
                    [STAGE {C.stage + 1}]
                  </button>
                )}
              </div>
            )}
            {/* Evolve strip */}
            <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
              <input type="text" value={C.evolveHint}
                onChange={(e) => C.setEvolveHint(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && C.evolveHint.trim()) { e.preventDefault(); void C.evolveLab() } }}
                placeholder="--evolve [+ hex viewer | + sniffer | + difficulté]"
                style={{
                  flex: 1, background: '#000', color: RED,
                  border: `1px solid ${RED_BORDER}`, padding: '4px 8px',
                  fontFamily: 'inherit', fontSize: 11,
                }} />
              <VoicePushToTalk
                onTranscript={(text) => C.setEvolveHint((C.evolveHint ? C.evolveHint + ' ' : '') + text)}
                label="Dicter la mutation du lab cyber"
                disabled={C.labLoading}
                variant="ghost"
                size={28}
              />
              <AlertBtn onClick={() => void C.evolveLab()}
                disabled={!C.evolveHint.trim() || C.labLoading}>EVOLVE</AlertBtn>
            </div>
          </>
        ) : (
          <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.7, color: PINK, flex: 1 }}>
{`master@aurora:~$ aurora dojo --kata ${C.activeId}
┌── target :: ${C.active.name}
├── ${'▓'.repeat(progressBars)}${'░'.repeat(Math.max(0, 25 - progressBars))} ${C.lab ? 64 : 0}%
├── corpus     :: rockyou.txt [INDEXED]
├── strategy   :: ${C.stance === 'offense' ? 'heuristic + dictionary' : 'detection + monitoring'}
├── difficulty :: ${'★'.repeat(C.active.difficulty)}${'☆'.repeat(3 - C.active.difficulty)}
├── stage      :: ${C.stage} / 4
└── xp         :: ${C.xp}

▸ Press [LAUNCH] to forge an interactive lab
${C.labLoading ? '▸ FORGING...' : ''}
${C.labError ? '✗ ERROR: ' + C.labError : ''}`}
          </pre>
        )}
        {/* v82fw : daily tip Cyber stencil — visible quand pas de lab forgé */}
        {!C.lab && !C.labLoading && (
          <div style={{
            marginTop: 8, padding: '6px 10px',
            fontSize: 11, fontFamily: 'Space Mono, monospace',
            color: PINK,
            background: 'rgba(255, 128, 128, 0.08)',
            border: `1px solid ${RED}`,
            lineHeight: 1.5,
          }}>
            {getDailyTip('cyber')}
          </div>
        )}
        <div style={{ marginTop: 'auto', paddingTop: 8 }}>
          <AlertBtn primary onClick={C.launchKata} disabled={C.labLoading}>
            {C.labLoading ? 'FORGING...' : C.lab ? 'RE-FORGE' : 'LAUNCH KATA'}
          </AlertBtn>
          {/* v82fh : random kata + forge auto (parité V1 v82ew) */}
          {!C.labLoading && (
            <span style={{ marginLeft: 8 }}>
              <AlertBtn onClick={() => void C.randomKataAndForge()}>⚡ RANDOM</AlertBtn>
            </span>
          )}
          {C.lab && (
            <span style={{ marginLeft: 8 }}>
              <AlertBtn onClick={C.reloadSandbox}>RELOAD</AlertBtn>
              <span style={{ marginLeft: 8 }}>
                <AlertBtn onClick={C.closeLab}>ABORT</AlertBtn>
              </span>
            </span>
          )}
        </div>
      </main>

      {/* Leaderboard sidebar */}
      <aside style={{ border: `1px solid ${RED_BORDER}`, padding: 10, overflowY: 'auto' }}>
        <div style={{ color: PINK, fontSize: 10, letterSpacing: '0.2em', marginBottom: 8 }}>// LEADERBOARD</div>
        {C.runsForActive.length === 0 ? (
          <div style={{ color: RED_DIM, fontSize: 10 }}>// no runs yet</div>
        ) : (
          C.runsForActive.slice(0, 5).map((r, i) => {
            const colors = [RED, AMBER, RED_DIM, RED_DIM, RED_DIM]
            return (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '24px 1fr 50px',
                padding: '6px 0', borderBottom: `1px dashed ${RED_BORDER}`,
              }}>
                <span style={{ color: colors[i] }}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ color: colors[i] }}>STG{r.stage} · {Math.round(r.durationMs / 1000)}s</span>
                <span style={{ color: colors[i], textAlign: 'right' }}>+{r.xpEarned}</span>
              </div>
            )
          })
        )}
        <div style={{ marginTop: 14, color: PINK, fontSize: 10, letterSpacing: '0.2em' }}>// OPS</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
          <AlertBtn onClick={C.launchKata} disabled={C.labLoading}>ARM</AlertBtn>
          <AlertBtn onClick={C.closeLab} disabled={!C.lab}>ABORT</AlertBtn>
          <AlertBtn onClick={C.advanceStage} disabled={!C.allDone}>NEXT</AlertBtn>
          <AlertBtn disabled>HINT</AlertBtn>
        </div>

        <div style={{ marginTop: 14, color: PINK, fontSize: 10, letterSpacing: '0.2em' }}>// BELT</div>
        <div style={{ marginTop: 6 }}>
          <div style={{ fontSize: 11, color: RED, marginBottom: 4 }}>{C.belt.toUpperCase()} → {C.beltNext.toUpperCase()}</div>
          <div style={{ height: 6, background: RED_BORDER, position: 'relative' }}>
            <div style={{
              position: 'absolute', inset: '0 0 0 0', width: `${C.beltProgress}%`,
              background: RED,
            }} />
          </div>
          <div style={{ fontSize: 10, color: RED_DIM, marginTop: 4 }}>
            {C.xp} / {C.nextThresh} XP
          </div>
        </div>
      </aside>

      {/* Bottom log */}
      <footer style={{
        gridColumn: '1 / -1', border: `1px solid ${RED_BORDER}`, padding: '8px 14px',
        fontSize: 10, color: RED_DIM, overflow: 'hidden',
      }}>
        <div style={{ color: PINK, letterSpacing: '0.2em', marginBottom: 4 }}>// SECURE.LOG</div>
        {C.logs.slice(-3).map((l) => (
          <div key={l.id} style={{
            color: l.tone === 'xp' ? GREEN : l.tone === 'attack' ? RED : RED_DIM,
          }}>
            {new Date().toTimeString().slice(0, 8)} ► {l.text}
          </div>
        ))}
      </footer>

      <style>{`@keyframes pulse { 50% { opacity: 0.5 } }`}</style>
    </div>
  )
}
