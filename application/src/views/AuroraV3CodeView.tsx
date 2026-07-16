/**
 * AuroraV3CodeView — Ricochet "AURORA.CODEX TERM/3 AMBER" entry.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-5.jsx
 * (CodeV3): pure-amber phosphor terminal on near-black, scanlines +
 * vignette, ASCII-bordered panels for two model outputs (LLAMA70B
 * active vs MISTRAL.L compare), Python diffusion sample, diff hunk
 * panel with green annotations, F1/F2/F3/F4/ESC footer hints.
 *
 * Real wiring: CodeView (2398 LOC) lazy-mounts on F2/click to keep
 * full feature parity (intent classifier, planning, sandbox, dev
 * server, 22 languages, R3F + GLSL playground).
 */
import { lazy, Suspense, useState } from 'react'
import '../styles/aurora-v3-code.css'

const CodeView = lazy(() => import('./CodeView'))

const AMBER = '#ffb947'
const AMBER_DIM = '#a87a3a'
const AMBER_LINE = '#5a3a14'
const BG = '#0a0500'
const GREEN = '#7df9c4'
const RED = '#c44'

const SAMPLE_LEFT = `#!/usr/bin/env python
"""diffuse the bamboo"""
import torch
from aurora import unet, sched

def diffuse(img, steps=50):
    x = torch.randn_like(img)
    for t in reversed(range(steps)):
        eps = unet(x, t)
        x = sched.step(eps, t, x)
    return decode(x)

# main
img = load("bamboo.png")
out = diffuse(img)
save(out, "out.png")  # OK`

const SAMPLE_RIGHT = `#!/usr/bin/env python
"""diffuse the bamboo"""
import torch
from aurora import unet, sched

def diffuse(img, steps=50):
    x = torch.randn_like(img)
    for t in reversed(range(steps)):
        eps = model(x, t, ctx)
        x = sched.prev(eps, t, x)
    return x.cpu()

# main
img = load("bamboo.png")
out = diffuse(img)
save(out, "out.png")  # CHECK`

export default function AuroraV3CodeView() {
  // v82an : `live` defaults to true so the real CodeView mounts
  // immediately (no preview gate). setLive remains in scope so the
  // dead preview JSX below still type-checks ; that block is never
  // reached at runtime since the early-return on live=true fires first.
  const [live, setLive] = useState(true)
  void setLive

  if (live) {
    return (
      <div data-v3-code-orchestrator="true">
        <Suspense fallback={
          <div style={{
            width: '100%', height: '100%',
            background: BG, color: AMBER,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'IBM Plex Mono, JetBrains Mono, monospace',
            letterSpacing: '0.3em', fontSize: 13,
          }}>AURORA.CODEX · LOADING ORCHESTRATOR…</div>
        }>
          <CodeView />
        </Suspense>
      </div>
    )
  }

  return (
    <div
      onKeyDown={(e) => { if (e.key === 'F2' || e.key === 'Enter') { e.preventDefault(); setLive(true) } }}
      tabIndex={0}
      style={{
        width: '100%', height: '100%',
        background: BG, color: AMBER,
        fontFamily: 'IBM Plex Mono, JetBrains Mono, Courier New, monospace',
        fontSize: 13, padding: 24, position: 'relative', overflow: 'hidden',
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, outline: 'none',
      }}>
      {/* Scanlines */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10,
        background: 'repeating-linear-gradient(0deg, transparent 0 2px, rgba(0,0,0,0.35) 2.5px, transparent 3px)',
      }} />
      {/* CRT vignette */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 11,
        background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 110%)',
      }} />

      <div style={{
        gridColumn: '1 / -1',
        borderBottom: `1px solid ${AMBER_LINE}`, paddingBottom: 6,
        fontSize: 11, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
      }}>
        <span>╔══ AURORA.CODEX ══ TERM/3 ══ AMBER ══</span>
        <span>USR:MASTER  MEM:24576K  9600 BAUD</span>
      </div>

      {[
        { name: 'LLAMA70B', cur: true, code: SAMPLE_LEFT, tok: '142', lat: '0.31s', verdict: 'PASS ✓', verdictColor: GREEN },
        { name: 'MISTRAL.L', cur: false, code: SAMPLE_RIGHT, tok: '128', lat: '0.42s', verdict: 'WARN', verdictColor: RED },
      ].map((m) => (
        <div key={m.name} style={{
          border: `1px solid ${AMBER_LINE}`, padding: 14, position: 'relative',
          background: 'rgba(255,185,71,0.02)',
          cursor: 'pointer',
        }} onClick={() => setLive(true)}>
          <div style={{
            fontSize: 10, marginBottom: 8,
            color: m.cur ? AMBER : AMBER_DIM,
          }}>
            {`> MODEL: ${m.name} ${m.cur ? '[★ ACTIVE]' : '[compare]'}`}
          </div>
          <pre style={{ margin: 0, lineHeight: 1.55, color: AMBER, whiteSpace: 'pre-wrap' }}>
            {m.code}
          </pre>
          <div style={{
            marginTop: 10, fontSize: 10, display: 'flex', justifyContent: 'space-between',
            borderTop: `1px dashed ${AMBER_LINE}`, paddingTop: 8,
          }}>
            <span>TOK {m.tok}</span>
            <span>LAT {m.lat}</span>
            <span style={{ color: m.verdictColor }}>{m.verdict}</span>
          </div>
        </div>
      ))}

      {/* Diff hunk */}
      <div style={{
        gridColumn: '1 / -1', border: `1px solid ${AMBER_LINE}`, padding: 14, fontSize: 12,
      }}>
        <div style={{ fontSize: 10, color: AMBER_DIM, marginBottom: 6 }}>{'> DIFF.HUNK [merged]'}</div>
        <pre style={{ margin: 0, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
{`@@ -3,5 +3,7 @@ def diffuse(img, steps=50):
-    x = torch.zeros_like(img)
+    x = torch.randn_like(img)            `}<span style={{ color: GREEN }}>{`# noise init`}</span>{`
     for t in reversed(range(steps)):
         eps = unet(x, t)
+        eps = guidance(eps, gamma=7.5)   `}<span style={{ color: GREEN }}>{`# CFG`}</span>{`
         x = sched.step(eps, t, x)`}
        </pre>
      </div>

      {/* Footer hints */}
      <div style={{
        gridColumn: '1 / -1', display: 'flex', gap: 14, fontSize: 11, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <span>{'>_ '}<span style={{ animation: 'cmd-blink 1s steps(2) infinite' }}>█</span></span>
        <span style={{ color: AMBER_DIM }}>F1 HELP · F2 ACCEPT · F3 REJECT · F4 NEXT · ESC EXIT</span>
        <span style={{ flex: 1 }} />
        <button type="button" onClick={() => setLive(true)}
          style={{
            background: AMBER, color: BG, border: 'none',
            padding: '6px 14px', fontSize: 11, letterSpacing: '0.2em',
            cursor: 'pointer', fontFamily: 'inherit',
          }}>[F2] LAUNCH ORCHESTRATOR</button>
      </div>

      <style>{`@keyframes cmd-blink { 50% { opacity: 0 } }`}</style>
    </div>
  )
}
